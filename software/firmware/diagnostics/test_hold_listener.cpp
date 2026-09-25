#define HOLD_ADMISSION_NO_MAIN
#include "test_hold_plan_admission.cpp"
#undef HOLD_ADMISSION_NO_MAIN
#include "hold_listener_owner.h"
#include "start_socket_session.h"
#include "start_listener.h"
#include <algorithm>
struct Network {
 std::vector<uint8_t> request;size_t cursor=0;
 bool pending=true,closed=false,eof=false,short_reply=false;
 int accepts=0,replies=0;
};
struct Client {Network* net=nullptr;int fd()const{return net?1:-1;}void stop(){if(net)net->closed=true;}};
struct Server {
 Network& net;bool up=false;
 void begin(){up=true;}void end(){up=false;}explicit operator bool()const{return up;}
 Client accept(){if(!up||!net.pending)return {};net.pending=false;++net.accepts;return {&net};}
};
struct Socket {
 Client& client;
 explicit Socket(Client& value):client(value){}
 int receive(uint8_t* out,size_t capacity){auto& net=*client.net;
   if(net.cursor==net.request.size())return net.eof?0:-2;
   const size_t count=std::min<size_t>(37,std::min(capacity,net.request.size()-net.cursor));
   memcpy(out,net.request.data()+net.cursor,count);net.cursor+=count;return int(count);
 }
 int send_once(const uint8_t*,size_t count){++client.net->replies;return int(count)-(client.net->short_reply?1:0);}
 void close(){client.stop();}
};
#ifndef HOLD_LISTENER_NO_MAIN
int main(int argc,char** argv){using namespace rocell_diag;
 assert(argc==2);std::ifstream file(argv[1],std::ios::binary);
 std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
 uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
 for(int scenario=0;scenario<5;++scenario){
  GuardedBus bus;Clock clock;clock.tick=1001;Crypto crypto;bool healthy=true;bus.healthy=&healthy;
  using Allocated=AllocatedHoldRuntime<GuardedBus,Clock,Crypto>;
  Allocated runtime;assert(runtime.initialize(bus,clock,crypto,key,boot,nonce,1000,10001000,
    policy(),"reviewed-hold",healthy_runtime,&healthy));
  Network net;net.eof=scenario==1;net.short_reply=scenario==2;
  std::string header="POST /rocell/diagnostics/start HTTP/1.1\r\nHost: test\r\nConnection: close\r\nContent-Type: application/octet-stream\r\nContent-Length: "+
    std::to_string(token.size())+"\r\n\r\n";
  net.request.assign(header.begin(),header.end());net.request.insert(net.request.end(),token.begin(),token.end());
  if(scenario==4)net.request.push_back('x');
  Server server{net};Client client;Socket socket{client};HoldListenerOwner<Allocated> owner(runtime);
  StartSocketSession<decltype(owner),Clock,Socket> connection(owner,clock,socket);
  StartListener<Server,Client,decltype(connection),decltype(owner),Clock> listener(server,client,connection,owner,clock,10001000);
  assert(listener.begin());assert(!listener.begin());
  if(scenario==3)clock.tick=10001000;
  for(int i=0;i<100;++i){clock.tick+=20000;listener.poll();}
  if(scenario==0){assert(listener.state()==ListenerState::Finished&&bus.writes==1&&runtime.size()==8);}
  else {assert(listener.state()==ListenerState::Fault&&bus.writes==0);}
  assert(net.accepts==(scenario==3?0:1));assert(net.replies==(scenario==3?0:1));
  const int reads=bus.reads;net.pending=true;listener.poll();assert(reads==bus.reads);
  assert(!server.up);
 }
}
#endif
