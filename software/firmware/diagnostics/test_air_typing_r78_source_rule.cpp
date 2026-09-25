#include "air_typing_r78_source_rule.h"
#include <cassert>
using rocell_diag::air_typing_r78_source_joint_verified;
int main(){
  // Leg three's stable, post-reset base readback is two counts above endpoint.
  assert(air_typing_r78_source_joint_verified(1985,1994,1987,1994));
  for(int delta=-3;delta<=3;++delta)
    assert(air_typing_r78_source_joint_verified(2000,2000,2000+delta,2000));
  assert(!air_typing_r78_source_joint_verified(2000,2000,2004,2000));
  assert(!air_typing_r78_source_joint_verified(2000,2000,1996,2000));
  assert(!air_typing_r78_source_joint_verified(1985,1994,1987,1995));
  assert(!air_typing_r78_source_joint_verified(1985,2000,1987,2000));
}
