#include <cassert>
#include <functional>
#include <map>
#include <string>
#include <cstdio>
using String=std::string;
const int HTTP_GET=0;
unsigned long esp_random(){static unsigned long value=0;return ++value;}
struct FakeServer {
  std::map<std::string,std::function<void()>> routes;
  std::string query,body,cache;int code=0;
  void on(const char* path,int method,std::function<void()> fn){assert(method==HTTP_GET);routes[path]=fn;}
  String arg(const char* name){assert(std::string(name)=="index");return query;}
  void sendHeader(const char*,const char* value){cache=value;}
  void send(int status,const char* type,const char* value){assert(std::string(type)=="application/json");code=status;body=value;}
} server;
#include "diagnostic_http.h"
int main(){
  registerDiagnosticRoutes();assert(server.routes.size()==2);
  server.routes.at("/rocell/diagnostics/status")();assert(server.code==200);puts(server.body.c_str());
  auto get=server.routes.at("/rocell/diagnostics/record");
  for(const char* bad:{"","-1","1x","100"," 1","+1"}) {
    server.query=bad;get();assert(server.code==400);
  }
  server.query="0";get();assert(server.code==404);
  assert(rocellDiagnosticEvidence.publish("converted","{\"example\":1}"));
  get();assert(server.code==200 && server.cache=="no-store");
  const auto original=server.body;puts(original.c_str());get();assert(server.body==original);
  assert(rocellDiagnosticEvidence.size()==1);
  assert(rocellDiagnosticSession.state()==rocell_diag::SessionState::Idle);
}
