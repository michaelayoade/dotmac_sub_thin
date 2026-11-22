"""sub_thin deploy/deploy-unit.toml against the dotmac.deploy_unit/1 contract (design rev3 sections 2.2, 2.7, 2.8).

Static checks on the committed descriptor and its sidecar spec. They read two
TOML files and one source file as text: no database, no network, no import of
the application. The Foundation read-back (`validate`) runs only where the
Foundation distribution is installed.

The contract checker below is written against the design document, not against
Control a18 (not yet built); it is deliberately small and refuses by name.
"""

from __future__ import annotations

import copy
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
UNIT_PATH = ROOT / "deploy" / "deploy-unit.toml"
SPEC_PATH = ROOT / "deploy" / "product.toml"

SCHEMA = "dotmac.deploy_unit/1"
PARAM_TYPES = frozenset(
    {
        "string",
        "int",
        "bool",
        "enum",
        "hostname",
        "cidr",
        "url",
        "duration_seconds",
        "path",
        "image_digest",
        "image_repository",
    }
)
WRITERS = frozenset({"generated", "operator", "ceremony", "integration"})
ROTATIONS = frozenset({"copy_only", "rotatable", "external_coordinated", "never"})
BINDING_STATES = frozenset({"pre_staged", "active"})
MATERIAL_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
# Products on Control's legacy_never list: refused at parse (section 2.2).
LEGACY_NEVER_PRODUCTS = frozenset({"dotmac-sub", "dotmac-integrator-companion"})
SECRET_NAME_HINT = re.compile(r"(SECRET|TOKEN|PASSWORD|KEY|DATABASE_URL|_DSN)$")
# Values a params file could never carry: secret-shaped content and estate addresses.
SECRET_SHAPED = re.compile(
    r"(-----BEGIN|bao://|hvs\.|s\.[A-Za-z0-9]{20,}|[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]+:[^@\s]+@)"
)
IPV4_LITERAL = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def _load(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _walk_strings(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for value in node.values() for s in _walk_strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in _walk_strings(value)]
    return []


def _bad_value(value: str) -> bool:
    """The grammar Foundation's env parser would otherwise alter (F1), plus secret shapes."""

    if "\n" in value or "\r" in value or "\x00" in value:
        return True
    if value != value.strip():
        return True
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return True
    return bool(SECRET_SHAPED.search(value))


def check_unit(
    unit: dict[str, Any],
    spec: dict[str, Any],
    *,
    companion_path: bool = False,
) -> list[str]:
    """Return refusal codes for a descriptor; empty means it satisfies the contract."""

    problems: list[str] = []
    if unit.get("schema") != SCHEMA:
        problems.append("schema")
    product = unit.get("product", "")
    if not product:
        problems.append("product")
    if unit.get("spec") != "deploy/product.toml" and not companion_path:
        problems.append("spec-path")
    if "spec_digest" in unit:
        # Digests are bound by the release record, never stored beside a sentinel image.
        problems.append("spec-digest-in-descriptor")

    # [image]: absent means transfer; pull is never self-declared (section 2.7).
    source = unit.get("image", {}).get("source", "transfer")
    if source not in {"transfer", "pull"}:
        problems.append("image-source")
    if source == "pull":
        problems.append("image-pull-requires-allowlist")

    materials = set(spec.get("runtime_materials", {}).get("names", []))
    params = unit.get("params", {})
    seen_materials: dict[str, str] = {}
    for name, param in params.items():
        if param.get("type") not in PARAM_TYPES:
            problems.append(f"param-type:{name}")
        material = param.get("material")
        if material is not None:
            if not MATERIAL_NAME.match(material):
                problems.append(f"param-material-name:{name}")
            if materials and material not in materials:
                problems.append(f"param-material-unknown:{name}")
            if material in seen_materials:
                problems.append(f"param-material-duplicate:{name}")
            seen_materials[material] = name
            if SECRET_NAME_HINT.search(material):
                problems.append(f"param-material-secret-class:{name}")
        for key in ("default", "pattern"):
            value = param.get(key)
            if isinstance(value, str) and key == "default" and _bad_value(value):
                problems.append(f"param-value:{name}")
        if param.get("type") == "duration_seconds" and "max" not in param:
            problems.append(f"param-unbounded:{name}")

    bindings = unit.get("bindings", [])
    binding_names: set[str] = set()
    active_binding_names: set[str] = set()
    for binding in bindings:
        name = binding.get("name", "")
        if not MATERIAL_NAME.match(name):
            problems.append(f"binding-name:{name}")
        if name in binding_names:
            problems.append(f"binding-duplicate:{name}")
        binding_names.add(name)
        if binding.get("state", "active") not in BINDING_STATES:
            problems.append(f"binding-state:{name}")
        elif binding.get("state", "active") == "active":
            active_binding_names.add(name)
        if binding.get("writer") not in WRITERS:
            problems.append(f"binding-writer:{name}")
        if binding.get("rotation") not in ROTATIONS:
            problems.append(f"binding-rotation:{name}")
        if not binding.get("roles") or not binding.get("kind"):
            problems.append(f"binding-incomplete:{name}")
        if "single_use" not in binding or not isinstance(binding["single_use"], bool):
            problems.append(f"binding-single-use:{name}")
        # A binding is a pointer: it never carries a value or a reference literal.
        if {"value", "secret_ref", "default"} & binding.keys():
            problems.append(f"binding-carries-value:{name}")
        if name in seen_materials:
            problems.append(f"binding-collides-with-param:{name}")

    legacy = unit.get("legacy_env_file")
    if legacy is not None:
        if product in LEGACY_NEVER_PRODUCTS or companion_path:
            problems.append("legacy-never")
        names = legacy.get("names", [])
        if not names or len(set(names)) != len(names):
            problems.append("legacy-names")
        for name in names:
            if not MATERIAL_NAME.match(name):
                problems.append(f"legacy-name-shape:{name}")
            if not SECRET_NAME_HINT.search(name):
                problems.append(f"legacy-nonsecret-name:{name}")
            if name in seen_materials or name == "APP_IMAGE":
                problems.append(f"legacy-collides-with-param:{name}")
            if name in active_binding_names:
                problems.append(f"legacy-collides-with-binding:{name}")
        if set(legacy) - {"names", "path_param"}:
            problems.append("legacy-extra-keys")
        path_param = params.get(legacy.get("path_param", ""), {})
        if (
            path_param.get("type") != "path"
            or "material" in path_param
            or "default" in path_param
        ):
            problems.append("legacy-path-param")

    for companion in unit.get("companions", []):
        if companion.get("order") != "after_primary_ready":
            problems.append("companion-order")
        if not isinstance(companion.get("required_at_switch"), bool):
            problems.append("companion-required-at-switch")
        if companion.get("host") not in {"same", "param"}:
            problems.append("companion-host")
        if not companion.get("product") or not companion.get("descriptor"):
            problems.append("companion-incomplete")

    for hold in unit.get("hold_points", []):
        timeout = params.get(hold.get("timeout_param", ""), {})
        if (
            timeout.get("type") != "duration_seconds"
            or timeout.get("max", 10**9) > 3600
        ):
            problems.append(f"hold-point-unbounded:{hold.get('name')}")

    for text in _walk_strings(unit):
        if SECRET_SHAPED.search(text):
            problems.append("secret-shaped-string")
        if IPV4_LITERAL.search(text):
            problems.append("ip-literal")
    return problems


def _unit() -> dict[str, Any]:
    return _load(UNIT_PATH)


def _spec() -> dict[str, Any]:
    return _load(SPEC_PATH)


def _check(unit: dict[str, Any]) -> list[str]:
    return check_unit(unit, _spec())


def test_descriptor_satisfies_the_contract() -> None:
    assert _check(_unit()) == []


def test_spec_is_the_sidecar_product_toml() -> None:
    unit = _unit()
    assert unit["spec"] == "deploy/product.toml"
    assert (ROOT / unit["spec"]).is_file()
    assert unit["product"] == _spec()["product"]
    stored = copy.deepcopy(unit)
    stored["spec_digest"] = "sha256:" + "1" * 64
    assert "spec-digest-in-descriptor" in _check(stored)
    moved = copy.deepcopy(unit)
    moved["spec"] = "deploy/other.toml"
    assert "spec-path" in _check(moved)


def test_spec_is_foundation_v3_or_later() -> None:
    assert _spec()["schema"] in {"ProductDeploymentSpec.v3", "ProductDeploymentSpec.v4"}


def test_image_source_default_transfer() -> None:
    unit = _unit()
    assert unit["image"]["source"] == "transfer"
    # An absent [image] table means transfer, not pull.
    absent = copy.deepcopy(unit)
    del absent["image"]
    assert _check(absent) == []
    # A descriptor cannot widen this by itself.
    pulled = copy.deepcopy(unit)
    pulled["image"]["source"] = "pull"
    assert "image-pull-requires-allowlist" in _check(pulled)
    other = copy.deepcopy(unit)
    other["image"]["source"] = "registry"
    assert "image-source" in _check(other)


def test_legacy_never_products() -> None:
    # sub_thin is a new build: runtime files only, no legacy bridge, no exceptions.
    unit = _unit()
    assert unit["product"] in LEGACY_NEVER_PRODUCTS
    assert "legacy_env_file" not in unit
    refused = copy.deepcopy(unit)
    refused["legacy_env_file"] = {
        "names": ["JWT_SECRET"],
        "path_param": "legacy_env_path",
    }
    assert "legacy-never" in _check(refused)
    # A bridge is refused for any product on the list and for any companion path.
    for product in sorted(LEGACY_NEVER_PRODUCTS):
        other = copy.deepcopy(refused)
        other["product"] = product
        assert "legacy-never" in _check(other)
    assert "legacy-never" in check_unit(refused, _spec(), companion_path=True)


def test_no_legacy_env_file_text_or_material_anywhere() -> None:
    for path in (UNIT_PATH, SPEC_PATH):
        text = path.read_text(encoding="utf-8")
        assert "[legacy_env_file]" not in text
        assert "path_param" not in text
    assert "LEGACY_DATABASE_URL" not in _spec()["runtime_materials"]["names"]


def test_bindings_are_pointers_never_values() -> None:
    unit = _unit()
    assert unit["bindings"]
    for binding in unit["bindings"]:
        assert {
            "name",
            "kind",
            "roles",
            "writer",
            "rotation",
            "single_use",
        } <= binding.keys()
        assert not {"value", "secret_ref", "default"} & binding.keys()
        assert binding.get("state", "active") == "active"
    leaky = copy.deepcopy(unit)
    leaky["bindings"][0]["secret_ref"] = "bao://production/dotmac-sub/kv/app/x"
    assert "binding-carries-value:" + leaky["bindings"][0]["name"] in _check(leaky)
    by_name = {b["name"]: b for b in unit["bindings"]}
    assert by_name["MIGRATION_DATABASE_URL"]["single_use"] is True
    assert by_name["DATABASE_URL"]["single_use"] is False
    assert "migrate" not in by_name["DATABASE_URL"]["roles"]


def test_every_secret_material_is_a_binding_not_a_param() -> None:
    unit = _unit()
    materials = set(_spec()["runtime_materials"]["names"])
    bound = {b["name"] for b in unit["bindings"]}
    param_materials = {
        p["material"] for p in unit["params"].values() if "material" in p
    }
    assert bound.isdisjoint(param_materials)
    # Together they cover every declared runtime material; the only extras are the
    # owner and backup credentials the spec names through migration and backup.
    assert materials <= bound | param_materials
    assert (bound | param_materials) - materials == {
        "MIGRATION_DATABASE_URL",
        "BACKUP_DATABASE_URL",
    }
    assert {
        _spec()["migration"]["owner_material"],
        _spec()["backup"]["datasets"][0]["material"],
    } == {
        "MIGRATION_DATABASE_URL",
        "BACKUP_DATABASE_URL",
    }
    clash = copy.deepcopy(unit)
    clash["params"]["clash"] = {"type": "string", "material": "TRUSTED_HOSTS"}
    assert any(p.startswith("param-material-duplicate") for p in _check(clash))
    collide = copy.deepcopy(unit)
    collide["bindings"][0]["name"] = "TRUSTED_HOSTS"
    assert "binding-collides-with-param:TRUSTED_HOSTS" in _check(collide)


def test_params_are_typed_and_refuse_unsafe_values() -> None:
    unit = _unit()
    assert {p["type"] for p in unit["params"].values()} <= PARAM_TYPES
    for value in (
        "a\nb",
        "nul\x00",
        " lead",
        "trail ",
        '"quoted"',
        "'quoted'",
        "bao://x/y",
        "-----BEGIN KEY",
    ):
        bad = copy.deepcopy(unit)
        bad["params"]["platform_root_domain"]["default"] = value
        assert "param-value:platform_root_domain" in _check(bad), repr(value)
    unknown = copy.deepcopy(unit)
    unknown["params"]["platform_root_domain"]["type"] = "secret"
    assert "param-type:platform_root_domain" in _check(unknown)
    secretish = copy.deepcopy(unit)
    secretish["params"]["platform_root_domain"]["material"] = "JWT_SECRET"
    assert "param-material-secret-class:platform_root_domain" in _check(secretish)


def test_seeding_is_fixed_off() -> None:
    seed = _unit()["params"]["seed_on_startup"]
    assert (
        seed["type"] == "bool"
        and seed["default"] is False
        and seed["choices"] == [False]
    )


def test_serving_role_never_receives_owner_or_backup_material() -> None:
    spec = _spec()
    (app,) = [r for r in spec["roles"] if r["code"] == "app"]
    assert "MIGRATION_DATABASE_URL" not in app["materials"]
    assert "BACKUP_DATABASE_URL" not in app["materials"]
    assert spec["migration"]["owner_material"] == "MIGRATION_DATABASE_URL"


def test_no_companions_jobs_or_hold_points() -> None:
    unit = _unit()
    assert not {"companions", "jobs", "hold_points"} & unit.keys()


def test_no_dotenv_and_no_env_file_anywhere_in_deploy() -> None:
    deploy = ROOT / "deploy"
    assert not [
        p for p in deploy.rglob("*") if p.name == ".env" or p.name.startswith(".env.")
    ]
    for path in (UNIT_PATH, SPEC_PATH):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*env_file\s*[:=]", text, re.MULTILINE), path.name
    assert not (deploy / "docker-compose.override.yml").exists()


def test_descriptor_holds_no_secret_shaped_value_or_host_address() -> None:
    for path in (UNIT_PATH, SPEC_PATH):
        for text in _walk_strings(_load(path)):
            assert not SECRET_SHAPED.search(text), path.name
            assert not IPV4_LITERAL.search(text), path.name


def test_foundation_validate_accepts_product_toml() -> None:
    # Skipped where the Foundation distribution is not installed; the read-back
    # is also run from a Starter source checkout when the descriptor changes.
    cli = pytest.importorskip("dotmac_deployment_foundation.cli")
    assert cli.main(["-f", str(SPEC_PATH), "validate"]) == 0
