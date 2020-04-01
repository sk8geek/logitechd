# SPDX-License-Identifier: MIT

from typing import Any, Callable, ClassVar, Dict, List, Tuple, Union

import logitechd.hidpp
import logitechd.protocol
import logitechd.protocol.base
import logitechd.utils


class _DocEnum(object):
    _str: ClassVar[Dict[int, str]] = {}

    @classmethod
    def get_str(cls, id: int) -> str:
        return cls._str.get(id, 'Unkown')


class _Features(_DocEnum):
    '''
    Lists HID++ 2.0 Features
    '''
    ROOT = 0x0001

    _str = {
        ROOT: 'IRoot',
    }


class _Functions(_DocEnum):
    '''
    Lists HID++ 2.0 Functions
    '''
    # IRoot
    GET_FEATURE = _Features.ROOT, 0
    GET_PROTOCOL_VERSION = _Features.ROOT, 1

    _str = {
        GET_PROTOCOL_VERSION[1]: 'version, ping = GetProtocolVersion(ping)',
    }


def hiddp_request(function: Tuple[int, int], sw_id: int = 0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    '''
    This decorator constructs a HID++ message with the requested HID++ 2.0
    function and passes it to the python function. It also injects a docstring
    to the function.
    '''

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(protocol: logitechd.protocol.base.BaseProtocol, *args: Any, **kwargs: Any) -> Any:
            assert isinstance(protocol, logitechd.protocol.base.BaseProtocol)
            assert 'msg' not in kwargs

            kwargs['msg'] = HIDPP20.Message(
                report_id=0x10,
                device_index=protocol._index,
                feature_index=function[0],
                function=function[1],
                sw_id=protocol.sw_id,
            )

            return func(protocol, *args, **kwargs)
        wrapper.__doc__ = f'HID++ 2.0 function wrapper\n\n' \
                          f'Feature: {_Features.get_str(function[0])} (0x{function[0]:04x})\n' \
                          f'Function: ({function[1]}) {_Functions.get_str(function[1])}'
        return wrapper
    return decorator


class HIDPP20(logitechd.protocol.base.BaseProtocol):
    '''
    Represents the HID++ 2.0 protocol
    '''
    features = _Features
    functions = _Functions

    class Message(object):
        '''
        HID++ 2.0 message
        '''
        def __init__(self, report_id: int, device_index: int, feature_index: int,
                     function: int, sw_id: int = 0, args: List[int] = []):
            self.report_id = report_id
            self.device_index = device_index
            self.feature_index = feature_index
            self.function = function
            self.sw_id = sw_id

            args_len = logitechd.hidpp.REPORT_SIZE[self.report_id] - 4

            assert len(args) <= args_len
            self.args = logitechd.utils.ljust(args, args_len)

        def __repr__(self) -> str:
            return f'Message(report=0x{self.report_id:02x}, device={self.device_index},' \
                    f'feature=0x{self.feature_index:04x}, function={self.function}, sw_id={self.sw_id}, ' \
                    f'args=[{" ".join(f"0x{byte:02x}" for byte in self.args)}])'

        @property
        def buffer(self) -> List[int]:
            '''
            Message buffer
            '''
            buf: List[Union[List[int], int]] = [
                self.report_id,
                self.device_index,
                self.feature_index,
                self.function << 8 + self.sw_id & 0xf,
                self.args,
            ]
            return logitechd.utils.ljust(logitechd.utils.flatten(buf), logitechd.hidpp.REPORT_SIZE[self.report_id])

        @classmethod
        def from_buffer(cls, buf: List[int]) -> 'HIDPP20.Message':
            '''
            Instanciates a HID++ 2.0 message from a message buffer
            '''
            assert len(buf) == logitechd.hidpp.REPORT_SIZE[buf[0]]
            return cls(
                report_id=buf[0],
                device_index=buf[1],
                feature_index=buf[2],
                function=buf[3] >> 8,
                sw_id=buf[3] & 0xf,
                args=buf[4:]
            )

    def _command(self, msg: 'HIDPP20.Message') -> 'HIDPP20.Message':
        '''
        Sends a message to the device and return the response
        '''
        return self.Message.from_buffer(msg.buffer)

    @hiddp_request(functions.GET_PROTOCOL_VERSION)
    def ping(self, data: int, msg: 'HIDPP20.Message') -> int:
        msg.args[2] = data

        ret = self._command(msg)

        return ret.args[2]
