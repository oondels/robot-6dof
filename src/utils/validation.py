from scservo_sdk import COMM_SUCCESS


def validate_result(servo, result, error, operation: str):
    if result != COMM_SUCCESS:
        raise RuntimeError(
            f"{operation}: {servo.getTxRxResult(result)}"
        )

    if error != 0:
        raise RuntimeError(
            f"{operation}: {servo.getRxPacketError(error)}"
        )
