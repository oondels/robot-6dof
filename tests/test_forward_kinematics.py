import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from math import sqrt
from pathlib import Path
from types import MappingProxyType

from src.application import Joint, JointConfig, RobotArm
from src.application.kinematics import (
    DHJoint,
    KinematicConfig,
    dh_transform,
    forward_kinematics,
)


def planar_config() -> KinematicConfig:
    """Fixture sintética; não descreve o arm-test1."""
    return KinematicConfig(
        convention="standard_dh",
        distance_unit="mm",
        angle_unit="deg",
        base_frame="planar_base",
        end_frame="planar_tip",
        partial=False,
        chain=(
            DHJoint("j1", theta_offset_deg=0, d_mm=0, a_mm=100, alpha_deg=0),
            DHJoint("j2", theta_offset_deg=0, d_mm=0, a_mm=50, alpha_deg=0),
        ),
    )


class ForwardKinematicsTestCase(unittest.TestCase):
    def assertMatrixAlmostEqual(self, actual, expected) -> None:
        self.assertEqual(len(actual), len(expected))
        for row, expected_row in zip(actual, expected):
            self.assertEqual(len(row), len(expected_row))
            for value, expected_value in zip(row, expected_row):
                self.assertAlmostEqual(value, expected_value, delta=1e-9)

    def test_identity(self) -> None:
        self.assertMatrixAlmostEqual(
            dh_transform(theta_deg=0, alpha_deg=0, a_mm=0, d_mm=0),
            ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
        )

    def test_translation_along_d(self) -> None:
        self.assertMatrixAlmostEqual(
            dh_transform(theta_deg=0, alpha_deg=0, a_mm=0, d_mm=83),
            ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 83), (0, 0, 0, 1)),
        )

    def test_translation_along_a(self) -> None:
        self.assertMatrixAlmostEqual(
            dh_transform(theta_deg=0, alpha_deg=0, a_mm=28, d_mm=0),
            ((1, 0, 0, 28), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
        )

    def test_theta_rotates_around_z(self) -> None:
        self.assertMatrixAlmostEqual(
            dh_transform(theta_deg=90, alpha_deg=0, a_mm=0, d_mm=0),
            ((0, -1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
        )

    def test_alpha_rotates_around_x(self) -> None:
        self.assertMatrixAlmostEqual(
            dh_transform(theta_deg=0, alpha_deg=90, a_mm=0, d_mm=0),
            ((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)),
        )

    def test_classical_dh_with_all_parameters(self) -> None:
        self.assertMatrixAlmostEqual(
            dh_transform(theta_deg=90, alpha_deg=90, a_mm=2, d_mm=3),
            ((0, 0, 1, 0), (1, 0, 0, 2), (0, 1, 0, 3), (0, 0, 0, 1)),
        )

    def test_negative_angles_and_signed_distances(self) -> None:
        self.assertMatrixAlmostEqual(
            dh_transform(theta_deg=-90, alpha_deg=-90, a_mm=-2, d_mm=-3),
            ((0, 0, 1, 0), (-1, 0, 0, 2), (0, -1, 0, -3), (0, 0, 0, 1)),
        )

    def test_non_right_angles_match_analytical_matrix(self) -> None:
        # sin(30)=cos(60)=1/2; cos(30)=sin(60)=sqrt(3)/2.
        self.assertMatrixAlmostEqual(
            dh_transform(theta_deg=30, alpha_deg=60, a_mm=2, d_mm=3),
            (
                (sqrt(3) / 2, -0.25, sqrt(3) / 4, sqrt(3)),
                (0.5, sqrt(3) / 4, -0.75, 1),
                (0, sqrt(3) / 2, 0.5, 3),
                (0, 0, 0, 1),
            ),
        )

    def test_planar_2r_analytical_positions_and_rotations(self) -> None:
        identity = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        rz90 = ((0, -1, 0), (1, 0, 0), (0, 0, 1))
        cases = (
            (0, 0, (150, 0, 0), identity),
            (90, 0, (0, 150, 0), rz90),
            (0, 90, (100, 50, 0), rz90),
        )
        for q1, q2, position, rotation in cases:
            with self.subTest(q1=q1, q2=q2):
                result = forward_kinematics(planar_config(), {"j1": q1, "j2": q2})
                self.assertMatrixAlmostEqual((result.position_mm,), (position,))
                self.assertMatrixAlmostEqual(result.rotation, rotation)
                self.assertMatrixAlmostEqual(
                    result.transform,
                    tuple(tuple(rotation[i]) + (position[i],) for i in range(3))
                    + ((0, 0, 0, 1),),
                )

    def test_nonplanar_composition_uses_accumulated_frame(self) -> None:
        config = replace(planar_config(), chain=(
            DHJoint("j1", 0, 3, 2, 90),
            DHJoint("j2", 0, 5, 4, 0),
        ))
        # Após Rx(90), a translação local de 5 em z passa a -5 em y da base.
        self.assertMatrixAlmostEqual(
            forward_kinematics(config, {"j1": 0, "j2": 90}).transform,
            ((0, -1, 0, 2), (0, 0, -1, -5), (1, 0, 0, 7), (0, 0, 0, 1)),
        )

    def test_theta_offset_is_added_to_physical_angle(self) -> None:
        config = replace(planar_config(), chain=(DHJoint("j1", -90, 0, 100, 0),))
        result = forward_kinematics(config, {"j1": 180})
        self.assertMatrixAlmostEqual((result.position_mm,), ((0, 100, 0),))

    def test_angles_are_associated_by_name_not_mapping_order(self) -> None:
        result = forward_kinematics(
            planar_config(), MappingProxyType({"j2": 90, "j1": 0})
        )
        self.assertMatrixAlmostEqual((result.position_mm,), ((100, 50, 0),))

    def test_missing_joint_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ausentes=.*j2"):
            forward_kinematics(planar_config(), {"j1": 0})

    def test_unexpected_joint_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "inesperadas=.*gripper"):
            forward_kinematics(planar_config(), {"j1": 0, "j2": 0, "gripper": 0})

    def test_names_are_exact(self) -> None:
        with self.assertRaises(ValueError):
            forward_kinematics(planar_config(), {"J1": 0, "j2": 0})

    def test_invalid_input_types(self) -> None:
        with self.assertRaises(TypeError):
            forward_kinematics(None, {})
        with self.assertRaises(TypeError):
            forward_kinematics(planar_config(), [0, 0])
        with self.assertRaises(TypeError):
            forward_kinematics(planar_config(), {1: 0, "j2": 0})

    def test_angles_must_be_finite_numbers(self) -> None:
        for value in (True, False, None, "90", [], float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    forward_kinematics(planar_config(), {"j1": value, "j2": 0})

    def test_individual_transform_validates_all_parameters(self) -> None:
        for field in ("theta_deg", "alpha_deg", "a_mm", "d_mm"):
            for value in (True, "0", None, float("nan"), float("inf")):
                with self.subTest(field=field, value=value):
                    args = dict(theta_deg=0, alpha_deg=0, a_mm=0, d_mm=0)
                    args[field] = value
                    with self.assertRaises((TypeError, ValueError)):
                        dh_transform(**args)

    def test_intermediate_transforms_are_accumulated_and_ordered(self) -> None:
        result = forward_kinematics(planar_config(), {"j1": 90, "j2": -90})
        self.assertEqual(result.joint_names, ("j1", "j2"))
        self.assertEqual(len(result.accumulated_transforms), 2)
        self.assertMatrixAlmostEqual(
            result.accumulated_transforms[0],
            ((0, -1, 0, 0), (1, 0, 0, 100), (0, 0, 1, 0), (0, 0, 0, 1)),
        )
        self.assertMatrixAlmostEqual(
            result.accumulated_transforms[1],
            ((1, 0, 0, 50), (0, 1, 0, 100), (0, 0, 1, 0), (0, 0, 0, 1)),
        )
        self.assertEqual(result.transform, result.accumulated_transforms[-1])

    def test_partial_chain_preserves_frame_metadata(self) -> None:
        config = replace(planar_config(), partial=True, end_frame="dh_1", chain=(planar_config().chain[0],))
        result = forward_kinematics(config, {"j1": 0})
        self.assertTrue(result.partial)
        self.assertEqual(result.base_frame, "planar_base")
        self.assertEqual(result.end_frame, "dh_1")
        self.assertEqual(result.joint_names, ("j1",))

    def test_inputs_and_previous_results_are_not_mutated(self) -> None:
        angles = {"j1": 0, "j2": 0}
        first = forward_kinematics(planar_config(), angles)
        self.assertEqual(angles, {"j1": 0, "j2": 0})
        angles["j1"] = 90
        forward_kinematics(planar_config(), angles)
        self.assertMatrixAlmostEqual((first.position_mm,), ((150, 0, 0),))
        with self.assertRaises(FrozenInstanceError):
            first.partial = True
        with self.assertRaises(TypeError):
            first.transform[0][0] = 99

    def test_joint_direction_is_not_applied_twice(self) -> None:
        class FakeServoBus:
            def __init__(self):
                self.read_ids = []

            def read_position(self, servo_id):
                self.read_ids.append(servo_id)
                return 1024

        bus = FakeServoBus()
        calibration = JointConfig(
            name="j1", servo_id=7, zero_position=2048, direction=-1,
            min_angle=-90, max_angle=90,
        )
        arm = RobotArm(bus, [Joint(calibration, bus)])
        angles = arm.current_angles()
        self.assertEqual(angles, {"j1": 90.0})
        config = replace(planar_config(), chain=(planar_config().chain[0],))
        result = forward_kinematics(config, angles)
        self.assertMatrixAlmostEqual((result.position_mm,), ((0, 100, 0),))
        self.assertEqual(bus.read_ids, [7])

    def test_overflow_is_rejected(self) -> None:
        config = replace(planar_config(), chain=(DHJoint("j1", 1e308, 0, 0, 0),))
        with self.assertRaises(ValueError):
            forward_kinematics(config, {"j1": 1e308})
        config = replace(planar_config(), chain=(
            DHJoint("j1", 0, 0, 1e308, 0), DHJoint("j2", 0, 0, 1e308, 0),
        ))
        with self.assertRaisesRegex(ValueError, "Composição"):
            forward_kinematics(config, {"j1": 0, "j2": 0})

    def test_import_and_calculation_need_only_standard_library(self) -> None:
        # Novo processo para não esconder imports por módulos já presentes no cache.
        code = '''
import sys
class BlockDependencies:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'scservo_sdk', 'serial', 'evdev', 'pynput', 'yaml', 'numpy'}:
            raise AssertionError('Dependência indevida: ' + fullname)
sys.meta_path.insert(0, BlockDependencies())
from src.application.kinematics import DHJoint, KinematicConfig, forward_kinematics
c = KinematicConfig('standard_dh', 'mm', 'deg', 'base', 'tip', False, (DHJoint('j', 0, 0, 1, 0),))
assert forward_kinematics(c, {'j': 0}).position_mm == (1.0, 0.0, 0.0)
'''
        completed = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class KinematicConfigTestCase(unittest.TestCase):
    def test_dh_parameters_must_be_numeric_and_finite(self) -> None:
        for field in ("theta_offset_deg", "alpha_deg", "a_mm", "d_mm"):
            for value in (True, "0", None, float("nan"), float("inf"), -float("inf"), 10 ** 400):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        replace(planar_config().chain[0], **{field: value})

    def test_names_must_be_explicit_and_nonempty(self) -> None:
        for name in ("", " j1", "j1 ", None, 1):
            with self.subTest(name=name):
                with self.assertRaises((TypeError, ValueError)):
                    DHJoint(name, 0, 0, 0, 0)

    def test_unsupported_convention(self) -> None:
        with self.assertRaisesRegex(ValueError, "Convenção"):
            replace(planar_config(), convention="modified_dh")

    def test_unsupported_units(self) -> None:
        for values in ({"distance_unit": "m"}, {"angle_unit": "rad"}):
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, "Unidades"):
                    replace(planar_config(), **values)

    def test_frames_are_required_and_distinct(self) -> None:
        for values in ({"base_frame": ""}, {"end_frame": None}, {"end_frame": "planar_base"}):
            with self.subTest(values=values):
                with self.assertRaises((TypeError, ValueError)):
                    replace(planar_config(), **values)

    def test_partial_requires_boolean(self) -> None:
        for value in (None, 0, "false"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    replace(planar_config(), partial=value)

    def test_empty_or_invalid_chain(self) -> None:
        for chain in ((), [], None, "j1", {"j1": 1}, (None,)):
            with self.subTest(chain=chain):
                with self.assertRaises((TypeError, ValueError)):
                    replace(planar_config(), chain=chain)

    def test_duplicate_joints(self) -> None:
        link = planar_config().chain[0]
        with self.assertRaisesRegex(ValueError, "duplicados"):
            replace(planar_config(), chain=(link, link))

    def test_configuration_copies_chain_and_is_immutable(self) -> None:
        chain = list(planar_config().chain)
        config = replace(planar_config(), chain=chain)
        chain.clear()
        self.assertEqual(len(config.chain), 2)
        self.assertIsInstance(config.chain[0].a_mm, float)
        with self.assertRaises(FrozenInstanceError):
            config.chain[0].a_mm = 0
        with self.assertRaises(FrozenInstanceError):
            config.partial = True


if __name__ == "__main__":
    unittest.main()
