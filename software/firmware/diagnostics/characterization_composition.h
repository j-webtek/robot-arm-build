// Single-task composition of controller, request authentication and all routes.
// Services/evidence must outlive this object. Allocate once per boot, off-stack.
#pragma once
#include "characterization_controller.h"
#include "characterization_authenticated_web.h"
#include "characterization_routes.h"
#include "characterization_prepare_routes.h"
#include "characterization_recovery_route.h"
#include "fixed_pair_reanchor_routes.h"
#include "park_step_routes.h"
#include "park_reanchor_routes.h"
#include "large_pose_lift_routes.h"
#include "large_pose_relief_routes.h"
namespace rocell_diag {
template<class Crypto,class Services,class Clock,class Web> class CharacterizationComposition {
  using Controller=CharacterizationController<Crypto,Services>;
  using Gate=CharacterizationRequestAuth<Crypto>;
  using AuthWeb=CharacterizationAuthenticatedWeb<Gate,Web>;
  struct Auth{AuthWeb& web;bool operator()(){return web.authenticated();}};
  struct Access{
    Controller& controller;AuthWeb& web;
    auto operator()(){return web.authenticated()?controller.session():nullptr;}
  };
  using Transport=CharacterizationTransport<Access,Clock>;
 public:
  CharacterizationComposition(Crypto& crypto,Services& services,Clock& clock,Web& web,
      const uint8_t (&key)[32],const uint8_t (&boot)[16],const uint16_t (&bounds)[7][2],
      CharacterizationPattern pattern=CharacterizationPattern::Legacy,
      bool enable_fixed_reanchor=false,bool enable_park_step=false,
      bool enable_park_return=false,bool enable_large_pose_lift=false,
      bool enable_large_pose_relief=false)
      :controller_(crypto,services,pattern),gate_(crypto,key,boot),web_(gate_,web),auth_{web_},
       access_{controller_,web_},transport_(access_,clock),routes_(transport_,auth_,web_),
       preparation_(controller_,auth_,web_,bounds),recovery_(crypto,controller_,web,key,boot),
       reanchor_(crypto,services,clock,web_,boot),park_step_(crypto,services,clock,web_,boot),
       park_return_(crypto,services,clock,web_,boot),
       large_pose_lift_(crypto,services,clock,web_,boot),
       large_pose_relief_(crypto,services,clock,web_,boot),
       reanchor_enabled_(enable_fixed_reanchor),park_step_enabled_(enable_park_step),
       park_return_enabled_(enable_park_return&&!enable_fixed_reanchor&&
                            !enable_park_step),
       large_pose_lift_enabled_(enable_large_pose_lift&&!enable_fixed_reanchor&&
                                !enable_park_step&&!enable_park_return&&!enable_large_pose_relief),
       large_pose_relief_enabled_(enable_large_pose_relief&&!enable_fixed_reanchor&&
                                  !enable_park_step&&!enable_park_return&&!enable_large_pose_lift){}
  void register_routes(){web_.collect_headers();routes_.register_routes();preparation_.register_routes();recovery_.register_route();if(reanchor_enabled_)reanchor_.register_routes();if(park_step_enabled_)park_step_.register_routes();if(park_return_enabled_)park_return_.register_routes();if(large_pose_lift_enabled_)large_pose_lift_.register_routes();if(large_pose_relief_enabled_)large_pose_relief_.register_routes();}
  void poll(){if(large_pose_relief_enabled_&&large_pose_relief_.claimed())large_pose_relief_.poll();else if(large_pose_lift_enabled_&&large_pose_lift_.claimed())large_pose_lift_.poll();else if(park_return_enabled_&&park_return_.claimed())park_return_.poll();else if(park_step_enabled_&&park_step_.claimed())park_step_.poll();else if(reanchor_enabled_&&reanchor_.claimed())reanchor_.poll();else controller_.poll();}
  // Trusted owner-task seam; intentionally not an HTTP route.
  size_t recovery_snapshot(char* output,size_t capacity){return controller_.recovery_snapshot(output,capacity);}
 private:
  Controller controller_;Gate gate_;AuthWeb web_;Auth auth_;Access access_;Transport transport_;
  CharacterizationRoutes<Transport,Auth,AuthWeb> routes_;
  CharacterizationPrepareRoutes<Controller,Auth,AuthWeb> preparation_;
  CharacterizationRecoveryRoute<Crypto,Controller,Web> recovery_;
  FixedPairReanchorRoutes<Crypto,Services,Clock,AuthWeb> reanchor_;
  ParkStepRoutes<Crypto,Services,Clock,AuthWeb> park_step_;
  ParkReanchorRoutes<Crypto,Services,Clock,AuthWeb> park_return_;
  LargePoseLiftRoutes<Crypto,Services,Clock,AuthWeb> large_pose_lift_;
  LargePoseReliefRoutes<Crypto,Services,Clock,AuthWeb> large_pose_relief_;
  bool reanchor_enabled_=false,park_step_enabled_=false,park_return_enabled_=false;
  bool large_pose_lift_enabled_=false;
  bool large_pose_relief_enabled_=false;
};
}
