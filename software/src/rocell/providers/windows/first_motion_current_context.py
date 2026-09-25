"""Current commissioning identity from reviewed persistent USB metadata.

Shares metadata resolution/freshness/reference checks with the endpoint reader,
but emits only the separate commissioning context type. Does not open a port.
Metadata is not proof of physical geometry, firmware identity or handle binding.
"""
from rocell.application.first_motion_contract import FirstMotionRequest
from rocell.safety.first_motion_review_authority import FirstMotionCurrentContext
from .endpoint_current_context import EndpointCurrentContextReader


class FirstMotionCurrentContextReader(EndpointCurrentContextReader):
    @staticmethod
    def _accept_request(request):
        return type(request) is FirstMotionRequest

    @staticmethod
    def _make_context(connection, identity, references, observed_ns, port):
        return FirstMotionCurrentContext(connection, identity, references, observed_ns, port)

    def __init__(self, request, *, binding, connection_id, metadata_reader,
                 references_reader, **kwargs):
        if (type(request) is not FirstMotionRequest
                or connection_id != request.to_dict()['attempt_id']):
            raise ValueError('Exact commissioning attempt identity required')
        super().__init__(request,binding=binding,connection_id=connection_id,
            metadata_reader=metadata_reader,references_reader=references_reader,**kwargs)
