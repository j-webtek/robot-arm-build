"""Stage four fixed noncontact A-side legs from reviewed r77; no upload."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


R77_COMPILE="wizard-20260924T230100683072Z-c19dfa5c3c31468fae31a8237f7830a4"
R77_APP_SHA="7a2059d76243b37e9b443c822093ef597611f136f5497a055f01278c3bcda496"
SOURCE_POSE="wizard-20260924T232712748224Z-e462f96c2c1b4561895acf10ba434231"
SOURCE_GAP="wizard-20260924T232837264746Z-8fdde03f975e4b17aca685ab9d0bf882"


def replace_one(data,old,new):
    if data.count(old)!=1:raise ValueError("Pinned marker absent or ambiguous")
    return data.replace(old,new)


OWNER_SOURCE_FAULT=b'''  const ShoulderPreloadPose* rejected_source(unsigned index)const{
    if(state_!=State::Fault||std::strcmp(reason_,"SOURCE_POSE_REJECTED")||
       count_!=3||index>=3)return nullptr;
    return &before_[index];
  }
'''

ROUTE_SOURCE_FAULT=b'''  static bool append(char* out,size_t capacity,size_t& used,const char* fmt,...){
    if(used>=capacity)return false;
    va_list args;va_start(args,fmt);
    const int n=vsnprintf(out+used,capacity-used,fmt,args);
    va_end(args);
    if(n<0||size_t(n)>=capacity-used)return false;
    used+=size_t(n);return true;
  }
  void source_fault(){
    if(!empty()){web_.send(400,"text/plain","");return;}
    char response[1200]={};size_t used=0;
    if(!owner_.rejected_source(0)||
       !append(response,sizeof(response),used,
         "{\\"schema\\":\\"rocell.air_source_fault.v1\\",\\"leg\\":%u,\\"samples\\":[",owner_.leg())){
      web_.send(409,"text/plain","");return;
    }
    for(unsigned n=0;n<3;++n){
      const auto* s=owner_.rejected_source(n);
      if(!s||!append(response,sizeof(response),used,
          "%s{\\"started_us\\":%llu,\\"finished_us\\":%llu,\\"positions\\":[",
          n?",":"",(unsigned long long)s->started_us,(unsigned long long)s->finished_us)){
        web_.send(500,"text/plain","");return;
      }
      for(int i=0;i<7;++i)if(!append(response,sizeof(response),used,"%s%u",i?",":"",s->position[i])){
        web_.send(500,"text/plain","");return;
      }
      if(!append(response,sizeof(response),used,"],\\"goals\\":[")){
        web_.send(500,"text/plain","");return;
      }
      for(int i=0;i<7;++i)if(!append(response,sizeof(response),used,"%s%u",i?",":"",s->goal[i])){
        web_.send(500,"text/plain","");return;
      }
      if(!append(response,sizeof(response),used,"],\\"torque\\":[")){
        web_.send(500,"text/plain","");return;
      }
      for(int i=0;i<7;++i)if(!append(response,sizeof(response),used,"%s%u",i?",":"",s->torque[i])){
        web_.send(500,"text/plain","");return;
      }
      if(!append(response,sizeof(response),used,"]}")){
        web_.send(500,"text/plain","");return;
      }
    }
    if(!append(response,sizeof(response),used,"]}")){
      web_.send(500,"text/plain","");return;
    }
    web_.send(200,"application/json",response);
  }
'''


def specialize(files,root):
    files=dict(files)
    files["air_typing_policy.h"]=(root/"firmware/diagnostics/air_typing_r78_policy.h").read_bytes()
    files["air_typing_r78_source_rule.h"]=(root/"firmware/diagnostics/air_typing_r78_source_rule.h").read_bytes()
    owner=replace_one(files["air_typing_owner.h"],b"RCAIRAB301",b"RCAIRAB401")
    owner=replace_one(owner,b"  unsigned leg()const{return leg_+1;}",
                      OWNER_SOURCE_FAULT+b"  unsigned leg()const{return leg_+1;}")
    files["air_typing_owner.h"]=owner
    routes=replace_one(files["air_typing_routes.h"],b'body!="AIR7"',b'body!="AIR4"')
    if routes.count(b"/rocell/air-type-final/")!=5:raise ValueError("Expected five r77 routes")
    routes=routes.replace(b"/rocell/air-type-final/",b"/rocell/air-type-last/")
    routes=replace_one(routes,b"#include <cstdio>",b"#include <cstdio>\n#include <cstdarg>")
    routes=replace_one(routes,
        b'    web_.on("/rocell/air-type-last/next",HTTP_POST,[this](){next();});',
        b'    web_.on("/rocell/air-type-last/next",HTTP_POST,[this](){next();});\n'
        b'    web_.on("/rocell/air-type-last/source-fault",HTTP_GET,[this](){source_fault();});')
    routes=replace_one(routes,b"  Crypto& crypto_;Services& services_;Clock& clock_;Web& web_;AirTypingOwner owner_;",
        ROUTE_SOURCE_FAULT+b"  Crypto& crypto_;Services& services_;Clock& clock_;Web& web_;AirTypingOwner owner_;")
    files["air_typing_routes.h"]=routes
    return files


def stage(root):
    root=Path(root).resolve();exports=root/"runs/wizard-exports"
    compiled,compile_digest=_read(exports,R77_COMPILE,"attachment-compile-review.json")
    source=root/".firmware-tools/configured-diagnostic-candidate-r77/RoArm-M3_example"
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    sha=lambda data:hashlib.sha256(data).hexdigest()
    prefix=".firmware-tools/configured-diagnostic-candidate-r77/RoArm-M3_example/"
    expected={Path(p).name:h for p,h in compiled["source_hashes"].items()
              if p.replace("\\","/").startswith(prefix)}
    image=(root/".firmware-tools/build-configured-diagnostic-candidate-r77--default-4mb-no-psram/RoArm-M3_example.ino.bin").read_bytes()
    pose,pose_digest=_read(exports,SOURCE_POSE,"attachment-pose-assessment.json")
    gap,gap_digest=_read(exports,SOURCE_GAP,"attachment-r77-source-gap.json")
    if (compiled["status"]!="COMPILED" or compiled["target"]!="configured-diagnostic-candidate-r77"
            or set(files)!=set(expected) or any(sha(data)!=expected[name] for name,data in files.items())
            or sha(image)!=R77_APP_SHA or pose["category"]!="STABLE_SAMPLED_POSE"
            or gap["would_pass_one_count_source_gate"] is not False
            or gap["would_pass_three_count_and_twelve_to_goal_gate"] is not True):
        raise ValueError("Pinned r77 predecessor or source evidence differs")
    candidate=specialize(files,root)
    target=root/".firmware-tools/configured-diagnostic-candidate-r78/RoArm-M3_example"
    target.mkdir(parents=True,exist_ok=True)
    existing={p.name:p.read_bytes() for p in target.iterdir() if p.is_file()}
    if existing and existing!=candidate:raise ValueError("Existing r78 stage differs; no overwrite")
    for name,data in candidate.items():
        if not (target/name).exists():
            with (target/name).open("xb") as stream:stream.write(data)
        if (target/name).read_bytes()!=data:raise ValueError("r78 staged readback differs")
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({"mode":"r78-air-typing-stage"},[],attachments={
        "r78-air-typing-stage.json":canonical(dict(predecessor_revision=77,
            predecessor_compile_export=R77_COMPILE,predecessor_compile_digest=compile_digest,
            source_pose_export=SOURCE_POSE,source_pose_digest=pose_digest,
            source_gap_export=SOURCE_GAP,source_gap_digest=gap_digest,
            selector="AIR4",maximum_writes=4,
            source_goals=[1994,2076,2038,2598,2234,2040,2047],
            source_positions=[1987,2082,2031,2600,2235,2041,2047],record_bytes=1130,
            changed_files={name:dict(before=sha(files[name]) if name in files else None,
                                     after=sha(data)) for name,data in candidate.items()
                           if data!=files.get(name)},
            hardware_access=False,uploaded=False,deployable=False))})
    if not verify_export(Path(saved["path"]))["valid"]:raise ValueError("Stage export invalid")
    return saved["path"]


if __name__=="__main__":print(stage(Path(__file__).resolve().parents[1]))
