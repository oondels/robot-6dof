import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from src.application.kinematics import forward_kinematics
from src.infrastructure.kinematics_loader import load_kinematic_config


# Robô planar sintético 2R. Não é a configuração física do arm-test1.
PLANAR_YAML = """\
convention: standard_dh
units:
  distance: mm
  angle: deg
base_frame: planar_base
end_frame: planar_tip
partial: false
chain:
  - joint: j1
    theta_offset_deg: 0
    d_mm: 0
    a_mm: 100
    alpha_deg: 0
  - joint: j2
    theta_offset_deg: 0
    d_mm: 0
    a_mm: 50
    alpha_deg: 0
"""


class KinematicsLoaderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "kinematics.yml"

    def load_text(self, text):
        self.path.write_text(text, encoding="utf-8")
        return load_kinematic_config(self.path)

    def load_data(self, data):
        return self.load_text(yaml.safe_dump(data))

    def test_loads_named_ordered_configuration_and_calculates_offline(self) -> None:
        config = self.load_text(PLANAR_YAML)
        self.assertEqual(config.convention, "standard_dh")
        self.assertEqual((config.distance_unit, config.angle_unit), ("mm", "deg"))
        self.assertEqual([link.joint for link in config.chain], ["j1", "j2"])
        self.assertFalse(config.partial)
        result = forward_kinematics(config, {"j2": 90, "j1": 0})
        for actual, expected in zip(result.position_mm, (100, 50, 0)):
            self.assertAlmostEqual(actual, expected, delta=1e-9)

    def test_accepts_string_path(self) -> None:
        self.path.write_text(PLANAR_YAML, encoding="utf-8")
        self.assertEqual(load_kinematic_config(str(self.path)).end_frame, "planar_tip")

    def test_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_kinematic_config(self.path)

    def test_empty_or_comment_only_file_is_pending_not_identity(self) -> None:
        for text in ("", "# Modelo pendente\n", "null\n"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "kinematics.yml"):
                    self.load_text(text)

    def test_invalid_yaml(self) -> None:
        with self.assertRaises(ValueError):
            self.load_text("chain: [\n")

    def test_rejects_non_mapping_root(self) -> None:
        for text in ("42", "[]", "- joint: j1"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "mapeamento"):
                    self.load_text(text)

    def test_rejects_missing_root_fields(self) -> None:
        original = yaml.safe_load(PLANAR_YAML)
        for field in original:
            with self.subTest(field=field):
                data = copy.deepcopy(original)
                del data[field]
                with self.assertRaisesRegex(ValueError, "ausentes"):
                    self.load_data(data)

    def test_rejects_unknown_root_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "desconhecidos"):
            self.load_text(PLANAR_YAML + "servo_id: 1\n")

    def test_units_must_be_explicit_and_supported(self) -> None:
        for units in (None, {}, {"distance": "mm"}, {"distance": "m", "angle": "deg"},
                      {"distance": "mm", "angle": "rad"},
                      {"distance": "mm", "angle": "deg", "time": "s"}):
            with self.subTest(units=units):
                data = yaml.safe_load(PLANAR_YAML)
                data["units"] = units
                with self.assertRaises(ValueError):
                    self.load_data(data)

    def test_rejects_modified_dh(self) -> None:
        with self.assertRaisesRegex(ValueError, "Convenção"):
            self.load_text(PLANAR_YAML.replace("standard_dh", "modified_dh"))

    def test_chain_must_be_nonempty_list(self) -> None:
        for chain in (None, {}, [], "j1", [None], [[0, 90, 28, 83]]):
            with self.subTest(chain=chain):
                data = yaml.safe_load(PLANAR_YAML)
                data["chain"] = chain
                with self.assertRaises(ValueError):
                    self.load_data(data)

    def test_rejects_missing_joint_fields(self) -> None:
        original = yaml.safe_load(PLANAR_YAML)
        for field in original["chain"][0]:
            with self.subTest(field=field):
                data = copy.deepcopy(original)
                del data["chain"][0][field]
                with self.assertRaisesRegex(ValueError, r"chain\[0\].*ausentes"):
                    self.load_data(data)

    def test_rejects_unknown_joint_fields(self) -> None:
        data = yaml.safe_load(PLANAR_YAML)
        data["chain"][0]["direction"] = -1
        with self.assertRaisesRegex(ValueError, "direction"):
            self.load_data(data)

    def test_rejects_pending_offsets(self) -> None:
        with self.assertRaisesRegex(ValueError, "theta_offset_deg"):
            self.load_text(PLANAR_YAML.replace("theta_offset_deg: 0", "theta_offset_deg: null"))

    def test_rejects_invalid_numeric_yaml_values(self) -> None:
        for value in ("true", '"100"', ".nan", ".inf", "-.inf"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "a_mm"):
                    self.load_text(PLANAR_YAML.replace("a_mm: 100", f"a_mm: {value}"))

    def test_rejects_duplicate_joint_names(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicados"):
            self.load_text(PLANAR_YAML.replace("joint: j2", "joint: j1"))

    def test_rejects_duplicate_yaml_keys_at_any_level(self) -> None:
        cases = (
            PLANAR_YAML + "convention: modified_dh\n",
            PLANAR_YAML.replace("  angle: deg", "  angle: deg\n  angle: rad"),
            PLANAR_YAML.replace("    a_mm: 100", "    a_mm: 100\n    a_mm: 999"),
        )
        for text in cases:
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "duplicada"):
                    self.load_text(text)

    def test_rejects_non_string_yaml_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "Chaves YAML"):
            self.load_text(PLANAR_YAML + "123: invalid\n")

    def test_rejects_yaml_merge_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "merges"):
            self.load_text(PLANAR_YAML + "<<: {convention: modified_dh}\n")

    def test_rejects_python_object_tags(self) -> None:
        with self.assertRaises(ValueError):
            self.load_text("!!python/object:builtins.object {}")

    def test_rejects_multiple_documents(self) -> None:
        with self.assertRaises(ValueError):
            self.load_text(PLANAR_YAML + "---\n" + PLANAR_YAML)

    def test_partial_chain_frame_metadata(self) -> None:
        data = yaml.safe_load(PLANAR_YAML)
        data.update(partial=True, end_frame="dh_1")
        data["chain"] = data["chain"][:1]
        result = forward_kinematics(self.load_data(data), {"j1": 0})
        self.assertTrue(result.partial)
        self.assertEqual(result.end_frame, "dh_1")

    def test_import_and_loading_do_not_import_hardware_or_main(self) -> None:
        self.path.write_text(PLANAR_YAML, encoding="utf-8")
        code = '''
import sys
class BlockHardware:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'scservo_sdk', 'serial', 'evdev', 'pynput', 'main', 'robot_config'}:
            raise AssertionError('Dependência indevida: ' + fullname)
sys.meta_path.insert(0, BlockHardware())
from src.infrastructure.kinematics_loader import load_kinematic_config
from src.application.kinematics import forward_kinematics
config = load_kinematic_config(sys.argv[1])
assert forward_kinematics(config, {'j1': 0, 'j2': 0}).position_mm == (150.0, 0.0, 0.0)
'''
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(self.path)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
