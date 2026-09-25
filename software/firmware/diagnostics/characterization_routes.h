// WebServer-compatible route binding. Auth must validate every request using
// reserved controller context. Registration never creates or advances a session.
#pragma once
#include "characterization_transport.h"
namespace rocell_diag {
template<class Transport,class Auth,class Web> class CharacterizationRoutes {
 public:
  CharacterizationRoutes(Transport& transport,Auth& auth,Web& web)
      :transport_(transport),auth_(auth),web_(web){}
  void register_routes(){
    if(registered_)return;registered_=true;
    bind("/rocell/characterization/start",HTTP_POST,CampaignRequest::Start,true);
    bind("/rocell/characterization/receipt",HTTP_POST,CampaignRequest::Receipt,true);
    bind("/rocell/characterization/record-info",HTTP_GET,CampaignRequest::RecordInfo,false);
    bind("/rocell/characterization/record-chunk",HTTP_POST,CampaignRequest::RecordChunk,true);
    bind("/rocell/characterization/fault",HTTP_GET,CampaignRequest::Fault,false);
  }
 private:
  void bind(const char* path,int method,CampaignRequest request,bool body_required){
    web_.on(path,method,[this,request,body_required](){handle(request,body_required);});
  }
  void handle(CampaignRequest request,bool body_required){
    web_.sendHeader("Cache-Control","no-store");
    if(!auth_()){web_.send(403,"text/plain","");return;}
    if(body_required?(web_.args()!=1||web_.argName(0)!="plain"):web_.args()!=0){
      web_.send(400,"text/plain","");return;
    }
    size_t size=0;
    if(body_required){
      auto body=web_.arg("plain");
      if(!body.length()||body.length()%2||body.length()>sizeof(input_)*2){web_.send(400,"text/plain","");return;}
      for(size_t i=0;i<body.length();++i){
        char c=body[i];int value=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
        if(value<0){memset(input_,0,sizeof(input_));web_.send(400,"text/plain","");return;}
        if(i%2)input_[i/2]|=value;else input_[i/2]=value<<4;
      }
      size=body.length()/2;
    }
    size_t written=0;int status=transport_.dispatch(request,input_,size,output_,sizeof(output_),written);
    memset(input_,0,sizeof(input_));
    const char* hex="0123456789abcdef";
    if(written>sizeof(output_)){web_.send(500,"text/plain","");return;}
    for(size_t i=0;i<written;++i){response_[2*i]=hex[output_[i]>>4];response_[2*i+1]=hex[output_[i]&15];}
    response_[2*written]=0;web_.send(status,"text/plain",response_);
  }
  Transport& transport_;Auth& auth_;Web& web_;bool registered_=false;
  uint8_t input_[512]={},output_[1024]={};char response_[2049]={};
};
}
