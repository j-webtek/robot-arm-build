// Offline transport dispatch seam. Access MUST authenticate the request and
// return only its reserved session. No bus or session advancement in handlers.
#pragma once
#include "characterization_session.h"
namespace rocell_diag {
enum class CampaignRequest { Start, Receipt, RecordInfo, RecordChunk, Fault };
template<class Access,class Clock> class CharacterizationTransport {
 public:
  CharacterizationTransport(Access& access,Clock& clock):access_(access),clock_(clock){}
  // Caller owns bounded request/response buffers. Returns HTTP-compatible status.
  int dispatch(CampaignRequest request,const uint8_t* body,size_t size,
               uint8_t* output,size_t capacity,size_t& written){
    written=0;
    auto* session=access_();if(!session)return 403;
    if(!output||capacity<1||(!body&&size))return 400;
    if(request==CampaignRequest::Start||request==CampaignRequest::Receipt){
      if(!size||size>512||(request==CampaignRequest::Receipt&&size!=124))return 400;
      bool ok=request==CampaignRequest::Start?session->start(body,size,clock_.now_us()):
        session->accept_export({body,size},clock_.now_us());
      output[0]=ok?1:0;written=1;return ok?200:409;
    }
    if(request==CampaignRequest::RecordInfo){
      if(size||capacity<35)return 400;
      unsigned leg;size_t length;uint8_t digest[32];
      if(!session->record_info(leg,length,digest))return 409;
      output[0]=uint8_t(leg);output[1]=uint8_t(length>>8);output[2]=uint8_t(length);
      memcpy(output+3,digest,32);written=35;return 200;
    }
    if(request==CampaignRequest::RecordChunk){
      if(size!=35||capacity>1024)return 400;
      uint8_t digest[32];memcpy(digest,body+3,32);
      const size_t offset=(size_t(body[1])<<8)|body[2];
      return session->record_chunk(body[0],digest,offset,output,capacity,written)?200:409;
    }
    if(request==CampaignRequest::Fault){
      if(size)return 400;
      written=encode_characterization_fault(session->fault(),output,capacity);
      return written?200:409;
    }
    return 400;
  }
 private:
  Access& access_;Clock& clock_;
};
}
