#define main prior_routes
#define Session PriorSession
#define Access PriorAccess
#include "test_shoulder_session_routes.cpp"
#undef Access
#undef Session
#undef main
#include "shoulder_fault_settling_routes.h"
struct Session {
 rocell_diag::SettlingState current=rocell_diag::SettlingState::Idle;
 unsigned starts=0,receipts=0;
 const char* boot_id(){return "11111111111111111111111111111111";}
 const char* command_id(){return "settle-test";}
 const char* reason(){return "TEST";}
 unsigned count(){return 0;}auto state(){return current;}
 const char* record(){return "{}";}
 bool begin(rocell_diag::ShoulderReceiptView r,uint64_t){assert(r.size==124);++starts;current=rocell_diag::SettlingState::Reading;return true;}
 bool receipt(rocell_diag::ShoulderReceiptView r,uint64_t){assert(r.size==124);++receipts;current=rocell_diag::SettlingState::Reading;return true;}
};
struct Access{Session* s=nullptr;Session* operator()(){return s;}};
int main(){
 Access access;Clock clock;Web web;Session session;
 rocell_diag::ShoulderFaultSettlingRoutes<Access,Clock,Web> routes(access,clock,web);
 routes.register_routes();routes.register_routes();assert(web.routes.size()==4);
 auto status=web.routes.at("/rocell/shoulder-settling/status");
 auto start=web.routes.at("/rocell/shoulder-settling/start");
 auto receipt=web.routes.at("/rocell/shoulder-settling/receipt");
 status();assert(web.status==409);access.s=&session;status();assert(web.status==200);
 start();assert(web.status==400&&session.starts==0);
 web.parameters=1;web.body=std::string(248,'z');start();assert(web.status==400&&session.starts==0);
 web.body=std::string(248,'0');start();assert(web.status==200&&session.starts==1);
 start();assert(web.status==409&&session.starts==1);
 receipt();assert(web.status==409&&session.receipts==0);
 session.current=rocell_diag::SettlingState::WaitingExport;receipt();assert(web.status==200&&session.receipts==1);
 web.parameters=0;status();assert(web.status==200&&session.receipts==1);
 std::cout<<"SETTLING_ROUTES_PASSED\n";
}
