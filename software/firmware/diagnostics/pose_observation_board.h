// Include after hold/pair/recovery declarations. No allocation or bus access
// until explicit route initialization after the boot identity is established.
#pragma once
#include "pose_observation_owner.h"
#include "pose_observation_routes.h"
#include <memory>
#include <new>
bool rocellReservePose(void*){
  if(rocellPoseReserved||rocellDiagnosticOwned||rocellHoldChallengeAttempted||
     rocellHoldConfigured||rocellRecoveryReserved||
     rocellPairRuntime.phase()!=rocell_diag::PairNetworkPhase::New||
     !rocellHoldHealthy(nullptr)||!rocellConfigurationBusInactive(nullptr))return false;
  rocellPoseReserved=true;rocellDiagnosticOwned=true;return true;
}
using RocellPoseOwner=rocell_diag::PoseObservationOwner<decltype(st),decltype(rocellConfiguredClock)>;
using RocellPoseRoutes=rocell_diag::PoseObservationRoutes<RocellPoseOwner,WebServer>;
std::unique_ptr<RocellPoseOwner> rocellPoseOwner;
std::unique_ptr<RocellPoseRoutes> rocellPoseRoutes;
void registerPoseObservationRoutes(){
  if(rocellPoseOwner)return;
  rocellPoseOwner.reset(new(std::nothrow) RocellPoseOwner(st,rocellConfiguredClock,
      rocellReservePose,nullptr,rocellDiagnosticInstance));
  if(!rocellPoseOwner)return;
  rocellPoseRoutes.reset(new(std::nothrow) RocellPoseRoutes(*rocellPoseOwner,server));
  if(rocellPoseRoutes)rocellPoseRoutes->register_routes();
}
void pollPoseObservation(){if(rocellPoseOwner)rocellPoseOwner->poll();}
