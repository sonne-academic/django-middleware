
class JsonRpcException(Exception):
    def __init__(self, code, message, data=None):
        self.code = code
        self.message = message
        self.data = data

    @property
    def error(self):
        err = {'code': self.code, 'message': self.message}
        if self.data and len(self.data) != 0:
            err['data'] = self.data
        return err


class JsonRpcParseError(JsonRpcException):
    def __init__(self, message, data=None):
        super().__init__(-32700, message, data)


class JsonRpcInvalidRequest(JsonRpcException):
    def __init__(self, message, data=None):
        super().__init__(-32600, message, data)


class JsonRpcMethodNotFound(JsonRpcException):
    def __init__(self, message, data=None):
        super().__init__(-32601, message, data)


class JsonRpcInvalidParams(JsonRpcException):
    def __init__(self, message, data=None):
        super().__init__(-32602, message, data)


class JsonRpcInternalError(JsonRpcException):
    def __init__(self, message, data=None):
        super().__init__(-32603, message, data)


class JsonRpcServerError(JsonRpcException):
    def __init__(self, message, data=None):
        super().__init__(-32000, message, data)
