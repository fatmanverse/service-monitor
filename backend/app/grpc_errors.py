from fastapi import HTTPException
import grpc


def abort_rpc(context, exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        code = {
            401: grpc.StatusCode.UNAUTHENTICATED,
            403: grpc.StatusCode.PERMISSION_DENIED,
            404: grpc.StatusCode.NOT_FOUND,
            409: grpc.StatusCode.FAILED_PRECONDITION,
            413: grpc.StatusCode.RESOURCE_EXHAUSTED,
            422: grpc.StatusCode.INVALID_ARGUMENT,
            429: grpc.StatusCode.RESOURCE_EXHAUSTED,
        }.get(exc.status_code, grpc.StatusCode.INTERNAL)
        context.set_code(code)
        context.set_details(str(exc.detail))
        return
    context.set_code(grpc.StatusCode.INTERNAL)
    context.set_details(str(exc))
