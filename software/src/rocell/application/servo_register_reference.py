"""Pure decoding for the pinned SMS_STS reference; never a bus access API.

This profile does not identify installed hardware. Values remain raw/count units
until a verified device profile supplies physical scaling and operating mode.
"""
from dataclasses import dataclass
from types import MappingProxyType

SOURCE_SHA256='b8b377642b3eb45610226fdf96fbc61d7c012a512bdd7f8c904a9c1ac88328af'
PROFILE_ID='waveshare-sms-sts-reference-'+SOURCE_SHA256[:12]


@dataclass(frozen=True)
class Register:
    address: int
    width: int
    sign_bit: int | None = None


REGISTERS=MappingProxyType({
    'model':Register(3,2), 'cw_deadband':Register(26,1), 'ccw_deadband':Register(27,1),
    'mode':Register(33,1), 'torque_enable':Register(40,1), 'acceleration':Register(41,1),
    'goal_position':Register(42,2), 'goal_speed':Register(46,2), 'torque_limit':Register(48,2),
    'position':Register(56,2,15), 'speed':Register(58,2,15), 'load':Register(60,2,10),
    'voltage':Register(62,1), 'temperature':Register(63,1), 'moving':Register(66,1),
    'current':Register(69,2,15)})
FEEDBACK_FIELDS=('position','speed','load','voltage','temperature','moving','current')


def decode_register(name,raw,*,read_status):
    if name not in REGISTERS:raise ValueError('Named reference register required')
    if read_status not in ('SUCCEEDED','FAILED','UNSUPPORTED'):
        raise ValueError('Explicit read status required')
    register=REGISTERS[name]
    if read_status!='SUCCEEDED':
        if raw is not None:raise ValueError('Unavailable read must not supply a cached value')
        value=None
    else:
        if type(raw) is not int or not 0<=raw<2**(8*register.width):
            raise ValueError('Unsigned raw register value required')
        # Mirror the library's sign-magnitude conversion, not two's complement.
        value=-(raw & ~(1<<register.sign_bit)) if register.sign_bit is not None and raw & (1<<register.sign_bit) else raw
    return dict(profile_id=PROFILE_ID,field=name,address=register.address,width=register.width,
        read_status=read_status,raw_unsigned=raw,decoded_value=value,units='RAW_REFERENCE',
        installed_compatibility_verified=False,physical_scaling_verified=False)


def decode_feedback_block(raw,*,read_status,byte_order):
    """Decode copied addresses 56..70 only after an explicitly successful read.

Byte order is supplied by a separately reviewed adapter, never guessed here.
No mode/goal value is read from this buffer: those addresses lie outside it.
"""
    if byte_order not in ('little','big'):raise ValueError('Explicit byte order required')
    if read_status=='SUCCEEDED':
        if type(raw) is not bytes or len(raw)!=15:raise ValueError('Complete 15-byte block required')
    elif raw is not None:raise ValueError('Failed block must not become fresh cached data')
    results={}
    for name in FEEDBACK_FIELDS:
        reg=REGISTERS[name];offset=reg.address-56
        word=int.from_bytes(raw[offset:offset+reg.width],byte_order) if raw is not None else None
        results[name]=decode_register(name,word,read_status=read_status)
    return results
