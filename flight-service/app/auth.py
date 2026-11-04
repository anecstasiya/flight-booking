import hmac
import os

import grpc


class AuthInterceptor(grpc.ServerInterceptor):
    def __init__(self):
        self.key = os.environ["GRPC_API_KEY"]
        if not self.key:
            raise ValueError("GRPC_API_KEY must not be empty")

    def intercept_service(self, continuation, details):
        handler = continuation(details)
        key = dict(details.invocation_metadata).get("x-api-key", "")
        if hmac.compare_digest(key, self.key):
            return handler

        def deny(request, context):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid API key")

        factory = (
            grpc.unary_stream_rpc_method_handler
            if handler and handler.response_streaming
            else grpc.unary_unary_rpc_method_handler
        )
        return factory(deny)
