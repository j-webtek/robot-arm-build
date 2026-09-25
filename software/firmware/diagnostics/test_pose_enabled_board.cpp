#define ROCELL_POSE_OBSERVATION 1
#define main legacy_board_fixture
#include "test_configured_pair_board_routes.cpp"
#undef main
int main(){
  // Registered pose endpoints must be allocated without reading files or bus.
  registerDiagnosticRoutes();assert(opens==0&&initializations==0);
  assert(server.routes.count("/rocell/pose/capture")&&server.routes.count("/rocell/pose/record"));
  assert(rocellPoseOwner&&rocellPoseRoutes);
  assert(!rocellReservePose(nullptr)); // Existing configured hold owns admission.
  rocellHoldConfigured=false;
  for(bool* conflict:{&rocellDiagnosticOwned,&rocellHoldChallengeAttempted,&rocellRecoveryReserved}){
    *conflict=true;assert(!rocellReservePose(nullptr));assert(!rocellPoseReserved);*conflict=false;
  }
  assert(rocellReservePose(nullptr));assert(rocellPoseReserved&&rocellDiagnosticOwned);
  assert(!rocellReservePose(nullptr));
  assert(!rocellConfigurationBusInactive(nullptr));
  // A claimed observation blocks pair preparation even if an old flag says hold
  // configured. No settings/key files or runtime initialization may be touched.
  rocellHoldConfigured=true;
  assert(!rocellPreparePair());assert(opens==0&&initializations==0);
  server.routes.at("/rocell/elbow-configuration/capture")();
  assert(opens==0&&initializations==0);
}
