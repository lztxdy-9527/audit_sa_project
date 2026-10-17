#!/usr/bin/env python
"""TASK-033 bounded facts integration, real renderer observations and accepted closure."""
from __future__ import annotations
import argparse
import builtins
import copy
import json
import sys
from pathlib import Path
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
TEST_ROOT=ROOT/"data/runtime_fact_packet_tests"

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

PREVIOUS=load(ROOT/"tests/test_runtime_rule_crosscheck.py","task033_accepted_helpers")
canon,sha,SCENES=PREVIOUS.canon,PREVIOUS.sha,PREVIOUS.SCENES

class Observer(PREVIOUS.Observer):
    def __init__(self,rt,e):
        self.facts_window=self.facts_inspecting=False
        super().__init__(rt,e)
        for name in ("run_gate2_fact_packet","inspect_gate2_fact_packet"):
            self.codes[getattr(rt,name).__code__]=name;self.counts[name]=self.api[name]=0
        self.wrap(rt,"inspect_gate2_rule_crosscheck","crosscheck_inspect")
        core=rt._load_frozen_facts_033()
        self.wrap(core,"build_fact_packet","facts_build")
        self.wrap(core,"render_markdown","facts_render")

    def wrap(self,module,name,label,forbidden=False):
        super().wrap(module,name,label,forbidden)
        if label not in ("crosscheck","facts_build","facts_render"): return
        real=getattr(module,name)
        def observed(*args,**kwargs):
            if self.facts_window and (label=="crosscheck" or (label=="facts_build" and self.facts_inspecting)):
                self.guard_hits.append(label+"_in_facts_inspect_or_window")
                raise AssertionError("facts must not recalculate or rebuild during inspect")
            start=len(self.e.CORE_RECORDS)
            role="inspect_display" if self.facts_inspecting else "build_internal"
            try: return real(*args,**kwargs)
            finally:
                if label=="facts_render":
                    for record in self.e.CORE_RECORDS[start:]:
                        if record["core"]==label: record["renderer_role"]=role
        setattr(module,name,observed)

def evidence_module():
    e=PREVIOUS.evidence_module();previous=e.build_candidate
    def build(*args,**kwargs):
        result=previous(*args,**kwargs);result["summary"]["task"]="TASK-033";return result
    e.build_candidate=build
    return e

def run(e,rt,obs,out):
    rid=out.name;runtime=ROOT/"data/runtime"/rid;gate1=ROOT/"data/human_gate_decision_records/gate1"/rid
    gate2=ROOT/"data/human_gate_decision_records/gate2"/rid;dbroot=ROOT/"data/sqlite_tests"/rid
    for root in (runtime,gate1,dbroot): root.mkdir(parents=True,exist_ok=False)
    batch=e.BATCH_NORMAL;source_before=SCENES([batch])
    assert sha((batch/"source/input.xlsx").read_bytes())=="8f6f2a989f3f3069e52ea495ebb6ce96a88e4c2537f9205f72491736c754a341"
    fixture=(ROOT/"data/decision_protocol_checks/task020r2_run_01/fixture_values.json").read_bytes()
    assert sha(fixture)=="6d8126aee3497a9c00cfee7493e2d04783e3284a61b911dd688bff29b433b337"
    g2fields=json.loads(fixture)["BASE2"]["submission"]

    def call(label,fn,*args,category="direct_public",**kwargs):
        before=copy.deepcopy(obs.counts)
        prior=obs.gate2,obs.screen_window,obs.crosscheck_window,obs.facts_window,obs.facts_inspecting
        obs.facts_window=label in ("facts","facts_inspect")
        obs.facts_inspecting=label=="facts_inspect"
        obs.crosscheck_window=obs.facts_window
        obs.gate2=obs.screen_window=obs.facts_window
        try:
            error,value,cid=e.call_api(rt,label,fn,*args,**kwargs)
            e.API_RECORDS[-1].update(record_category=category,reasons=copy.deepcopy(getattr(error,"reasons",None)),
                actual_entry_deltas={name:obs.counts[name]-before.get(name,0) for name in obs.counts})
            return error,copy.deepcopy(value),cid
        finally: obs.gate2,obs.screen_window,obs.crosscheck_window,obs.facts_window,obs.facts_inspecting=prior

    def setup(tag,crosscheck=True):
        leaf,scope=runtime/tag,gate1/tag;event=scope/"event_0001"
        error,_,_=call("registry",rt.build_runtime_registry,batch,leaf,scope_dir=scope)
        if error: raise error
        error,request,_=call("g1_prepare",rt.prepare_runtime_gate1_request,batch,leaf,"FIXTURE-REQ-G1-0001")
        if error: raise error
        material=request["request"]["materials"]
        sub=e.submission_for(e.APPROVE_FIELDS,material["materials_fingerprint"],"FIXTURE-REQ-G1-0001",material["batch_id"])
        error,record1,_=call("g1_save",rt.save_runtime_gate1_decision,batch,leaf,"FIXTURE-REQ-G1-0001",sub,event,scope_dir=scope)
        if error: raise error
        params=dict(scope_dir=scope,event_relative=event.relative_to(ROOT).as_posix(),database_path=dbroot/tag/"runtime.sqlite3")
        error,_,_=call("load",rt.run_gate1_approved_load,batch,leaf,**params)
        if error: raise error
        error,request2,_=call("g2_prepare",rt.prepare_runtime_gate2_request,batch,leaf,"FIXTURE-REQ-G2-0001",**params)
        if error: raise error
        sub2=copy.deepcopy(g2fields);sub2["batch_id"]=material["batch_id"]
        sub2["request_binding"]={"request_id":"FIXTURE-REQ-G2-0001","materials_binding":request2["request"]["materials"]["materials_fingerprint"]}
        sub2["prior_decision_binding"]={"wrapper_version":rt.GATE2_WRAPPER_VERSION,"record":record1["record"],"record_fingerprint":record1["record_fingerprint"]}
        event2=gate2/tag/"event_0001"
        error,_,_=call("g2_save",rt.save_runtime_gate2_decision,batch,leaf,"FIXTURE-REQ-G2-0001",sub2,event2,**params)
        if error: raise error
        params["gate2_event_relative"]=event2.relative_to(ROOT).as_posix()
        error,_,_=call("screen",rt.run_gate2_approved_screen,batch,leaf,**params)
        if error: raise error
        if crosscheck:
            error,_,_=call("crosscheck",rt.run_gate2_rule_crosscheck,batch,leaf,**params)
            if error: raise error
        return dict(leaf=leaf,scope=scope,event2=event2,params=params,output=leaf.with_name(tag+".facts"))

    def facts(scene,**overrides): return call("facts",rt.run_gate2_fact_packet,batch,scene["leaf"],**dict(scene["params"],**overrides))
    def inspect(scene): return call("facts_inspect",rt.inspect_gate2_fact_packet,batch,scene["leaf"],**scene["params"])
    def delta(): return e.API_RECORDS[-1]["actual_entry_deltas"]
    def sources(scene):
        return SCENES([batch,scene["leaf"],scene["scope"],scene["event2"],scene["params"]["database_path"].parent,
            *(scene["leaf"].with_name(scene["leaf"].name+suffix) for suffix in (".load",".screen",".crosscheck"))])

    normal=setup("normal",crosscheck=False)
    error,_,cid=facts(normal)
    e.check("G1.missing_crosscheck",isinstance(error,rt.RuntimeGate1Blocked) and error.field=="crosscheck_dir" and
        delta()["facts_build"]==0 and not normal["output"].exists(),{"call_id":cid,"field":getattr(error,"field",None)})
    error,_,_=call("crosscheck",rt.run_gate2_rule_crosscheck,batch,normal["leaf"],**normal["params"])
    if error: raise error
    before=sources(normal)
    error,_,cid=facts(normal,gate2_event_relative=normal["params"]["gate2_event_relative"].replace("event_0001","event_0002"))
    e.check("G1.wrong_gate2",isinstance(error,rt.RuntimeGate1Blocked) and delta()["facts_build"]==0 and not normal["output"].exists(),{"call_id":cid})
    database=normal["params"]["database_path"];raw_db=database.read_bytes();(out/"database.original.bin").write_bytes(raw_db)
    real_inspect,hit=rt.inspect_gate2_rule_crosscheck,[0]
    def inspected_then_change(*args,**kwargs):
        returned=real_inspect(*args,**kwargs);hit[0]+=1;database.write_bytes(raw_db+b"\n");return returned
    rt.inspect_gate2_rule_crosscheck=inspected_then_change
    try: error,_,cid=facts(normal)
    finally: rt.inspect_gate2_rule_crosscheck=real_inspect
    (out/"database.before_build.bad.bin").write_bytes(database.read_bytes());database.write_bytes(raw_db)
    e.check("G3.before_build",isinstance(error,rt.RuntimeGate1Blocked) and hit==[1] and delta()["facts_build"]==0 and
        not normal["output"].exists(),{"call_id":cid,"hit":hit[0],"field":getattr(error,"field",None)})
    error,recorded,run_id=facts(normal)
    if error: raise error
    semantics,real_eq=[],rt._require_equivalent_030
    def observe(value,expected,field):
        returned=real_eq(value,expected,field);semantics.append(field);return returned
    rt._require_equivalent_030=observe;hits=[]
    try:
        with PREVIOUS.PREVIOUS.PREVIOUS.PREVIOUS.readonly_guard(hits): error,restored,inspect_id=inspect(normal)
    finally: rt._require_equivalent_030=real_eq
    packet_path,md_path,artifact_path=(normal["output"]/name for name in ("fact_packet.json","fact_packet.md","artifacts.json"))
    packet_raw,md_raw,artifact_raw=packet_path.read_bytes(),md_path.read_bytes(),artifact_path.read_bytes()
    for label,raw in (("packet",packet_raw),("markdown",md_raw),("artifacts",artifact_raw)): (out/(label+".original.bin")).write_bytes(raw)
    packet=json.loads(packet_raw)
    built=next(item for item in e.CORE_RECORDS if item["core"]=="facts_build" and item["caller_api"]==run_id)
    rendered_run=[item for item in e.CORE_RECORDS if item["core"]=="facts_render" and item["caller_api"]==run_id]
    rendered_inspect=[item for item in e.CORE_RECORDS if item["core"]=="facts_render" and item["caller_api"]==inspect_id]
    e.check("G1.normal",error is None and not hits and canon(recorded)==canon(restored) and len(recorded)==6 and
        len(recorded["artifacts"])==10 and len(recorded["boundaries"])==6 and all(v is False for v in recorded["boundaries"].values()) and
        len(list(normal["output"].iterdir()))==4 and before==sources(normal),{"run":run_id,"inspect":inspect_id,"readonly_hits":hits})
    e.check("G1.real_build_and_renderer",canon(built["return"]["packet"])+b"\n"==packet_raw and
        built["return"]["markdown"].encode("utf-8")==md_raw and built["return"]["packet_sha256"]==sha(canon(packet)) and
        built["input_refs_before"]==built["input_refs_after"]==built["input_refs_api_end"] and
        len(rendered_run)==len(rendered_inspect)==1 and rendered_run[0]["return"].encode("utf-8")==md_raw and
        rendered_inspect[0]["return"].encode("utf-8")==md_raw and
        all(x["input_refs_before"]==x["input_refs_after"]==x["input_refs_api_end"] for x in rendered_run+rendered_inspect) and
        packet["summary"]["rule_counts"]=={"R01":0,"R02":1,"R03":0,"R04":0} and packet["summary"]["r02_overpayment_total_cents"]==400000,
        {"call_id":run_id,"build_delta":next(x for x in e.API_RECORDS if x["call_id"]==run_id)["actual_entry_deltas"]["facts_build"],
         "renderer_roles":[x["renderer_role"] for x in rendered_run+rendered_inspect]})
    started=json.loads((normal["output"]/"started.json").read_bytes())
    core=rt._load_frozen_facts_033()
    e.check("G1.original_notice_and_context",packet["banner"]==core.BANNER and packet["limits"]==core.LIMITS and
        "未实施正式契约与批准控制" in md_raw.decode("utf-8") and started["runtime_context"]==rt.FACT_RUNTIME_CONTEXT and
        len(started)==9 and len(started["bindings"])==13,{"core_notice_scope":started["runtime_context"]["core_notice_scope"]})
    error,_,cid=facts(normal)
    e.check("G1.repeat",isinstance(error,rt.RuntimeGate1Blocked) and error.field=="facts_dir" and delta()["facts_build"]==0,{"call_id":cid})
    last,hit=semantics[-1],[0]
    def late(value,expected,field):
        returned=real_eq(value,expected,field)
        if field==last: hit[0]+=1;md_path.write_bytes(md_raw+b"\n")
        return returned
    rt._require_equivalent_030=late
    try: error,_,cid=inspect(normal)
    finally: rt._require_equivalent_030=real_eq
    e.check("G3.inspect_late",isinstance(error,rt.RuntimeGate1Blocked) and error.field=="facts.fact_packet.md" and hit==[1] and
        not (normal["output"]/"failure.json").exists(),{"call_id":cid,"hit":hit[0],"last_semantic_field":last})
    (out/"markdown.late.bad.bin").write_bytes(md_path.read_bytes());retained,_,retained_id=inspect(normal)
    md_path.write_bytes(md_raw);clean,_,clean_id=inspect(normal)
    e.check("G3.retained_restored",retained is not None and clean is None and before==sources(normal),{"retained":retained_id,"restored":clean_id})
    bad_md=md_raw.replace("## 1. 总览".encode("utf-8"),"## 1. 修改总览".encode("utf-8"),1)
    assert bad_md!=md_raw
    md_path.write_bytes(bad_md);candidate=json.loads(artifact_raw)
    candidate.update(markdown_file_sha256=sha(bad_md),markdown_byte_size=len(bad_md));artifact_path.write_bytes(canon(candidate)+b"\n")
    error,_,cid=inspect(normal)
    (out/"markdown.synced.bad.bin").write_bytes(bad_md);(out/"markdown.synced.artifacts.bin").write_bytes(artifact_path.read_bytes())
    md_path.write_bytes(md_raw);artifact_path.write_bytes(artifact_raw)
    e.check("G2.renderer_relation",isinstance(error,rt.RuntimeGate1Blocked) and error.field=="facts.markdown.rendered_bytes" and
        delta()["facts_render"]==1 and delta()["facts_build"]==0,{"call_id":cid,"field":getattr(error,"field",None)})
    candidate=json.loads(packet_raw);candidate["next_step_allowed"]=0;bad=canon(candidate)+b"\n";packet_path.write_bytes(bad)
    a=json.loads(artifact_raw);a.update(packet_file_sha256=sha(bad),packet_canonical_sha256=sha(canon(candidate)))
    artifact_path.write_bytes(canon(a)+b"\n");error,_,cid=inspect(normal)
    (out/"packet.false_to_zero.bad.bin").write_bytes(bad);(out/"packet.false_to_zero.artifacts.bin").write_bytes(artifact_path.read_bytes())
    packet_path.write_bytes(packet_raw);artifact_path.write_bytes(artifact_raw)
    e.check("G2.strict_type",isinstance(error,rt.RuntimeGate1Blocked) and error.field=="facts.packet.next_step_allowed" and
        delta()["facts_render"]==0,{"call_id":cid,"field":getattr(error,"field",None)})
    candidate=json.loads(packet_raw);del candidate["findings"][0]["context"]["payable"]["record_id"]
    bad=canon(candidate)+b"\n";packet_path.write_bytes(bad);a=json.loads(artifact_raw)
    a.update(packet_file_sha256=sha(bad),packet_canonical_sha256=sha(canon(candidate)));artifact_path.write_bytes(canon(a)+b"\n")
    error,_,cid=inspect(normal)
    (out/"packet.missing_id.bad.bin").write_bytes(bad);(out/"packet.missing_id.artifacts.bin").write_bytes(artifact_path.read_bytes())
    packet_path.write_bytes(packet_raw);artifact_path.write_bytes(artifact_raw)
    e.check("G2.context_missing_id",isinstance(error,rt.RuntimeGate1Blocked) and
        error.field=="facts.packet.findings[0].context.payable.record_id" and delta()["facts_render"]==0,
        {"call_id":cid,"field":getattr(error,"field",None)})

    half_scene=setup("half_artifacts")
    real_open,half=builtins.open,{"hits":0}
    class HalfWriter:
        def __init__(self,stream): self.stream=stream
        def __enter__(self): self.stream.__enter__();return self
        def __exit__(self,*args): return self.stream.__exit__(*args)
        def __getattr__(self,name): return getattr(self.stream,name)
        def write(self,data):
            length=len(data)//2;self.stream.write(data[:length]);self.stream.flush()
            half.update(hits=half["hits"]+1,mode="xb",expected=len(data),written=length)
            raise OSError("TASK033_REAL_ARTIFACTS_HALF_WRITE")
    def opened(path,mode="r",*args,**kwargs):
        stream=real_open(path,mode,*args,**kwargs)
        if isinstance(path,(str,Path)) and Path(path)==half_scene["output"]/"artifacts.json" and mode=="xb": return HalfWriter(stream)
        return stream
    builtins.open=opened
    try: error,_,cid=facts(half_scene)
    finally: builtins.open=real_open
    diagnostic=json.loads((half_scene["output"]/"failure.json").read_bytes())
    e.check("G3.real_half",isinstance(error,rt.RuntimeGate1Error) and half["hits"]==1 and len(diagnostic)==6 and
        (half_scene["output"]/"artifacts.json").stat().st_size==half["written"] and any("OSError" in x for x in diagnostic["cause_chain"]),
        {"call_id":cid,"stage":getattr(error,"stage",None),"writer":half,"diagnostic":diagnostic})
    snapshot=SCENES([half_scene["output"]]);error,_,cid=inspect(half_scene)
    e.check("G3.failure_priority",isinstance(error,rt.RuntimeGate1Error) and error.stage.startswith("facts.failure.") and
        snapshot==SCENES([half_scene["output"]]) and delta()["facts_build"]==delta()["facts_render"]==0,{"call_id":cid})
    leaf,scope=runtime/"existing_empty",gate1/"existing_empty"
    error,_,_=call("registry",rt.build_runtime_registry,batch,leaf,scope_dir=scope)
    if error: raise error
    empty=leaf.with_name("existing_empty.facts");empty.mkdir()
    error,_,cid=call("facts",rt.run_gate2_fact_packet,batch,leaf,**normal["params"])
    e.check("G1.existing_empty",isinstance(error,rt.RuntimeGate1Blocked) and error.field=="facts_dir" and not list(empty.iterdir()),{"call_id":cid,"precondition_only":True})
    for cls,entry,mapped in ((core.FactPacketBlocked,"build_fact_packet",rt.RuntimeGate1Blocked),(core.FactPacketError,"render_markdown",rt.RuntimeGate1Error)):
        real=getattr(core,entry);reasons,hit=["controlled reason 1","controlled reason 2"],[0]
        def controlled(*args,**kwargs): hit[0]+=1;raise cls("TASK033_CONTROLLED_CLASS_MAPPING",reasons)
        setattr(core,entry,controlled)
        try: error,_,cid=call("mapping_helper",rt._call_frozen_entry,core,entry,{},category="helper_control")
        finally: setattr(core,entry,real)
        e.check("G3.mapping_"+cls.__name__,isinstance(error,mapped) and isinstance(error.__cause__,cls) and error.reasons==reasons and hit==[1],
            {"call_id":cid,"entry":entry,"hit":hit[0],"source":"controlled helper exception; original build/renderer entry not executed"})
    windows=[x for x in e.API_RECORDS if x["operation"] in ("facts","facts_inspect")]
    e.check("G4.forbidden_entries",not obs.guard_hits and all(all(x["actual_entry_deltas"].get(k,0)==0 for k in
        ("normalizer","loader","store_save","screen","crosscheck")) for x in windows) and
        all(x["actual_entry_deltas"]["facts_build"]==0 for x in windows if x["operation"]=="facts_inspect"),
        {"window_calls":len(windows),"guard_hits":obs.guard_hits})
    aliases={"inspect":"inspect_gate1_approved_load","gate1_verify":"verify_gate1_effective_approval",
        "screen_inspect":"inspect_gate2_approved_screen","crosscheck_inspect":"inspect_gate2_rule_crosscheck"}
    counts={name:{"entries":number,"profile":obs.counts[aliases.get(name,name)]} for name,number in obs.nested.items()}
    e.check("G4.count_closure",all(v["entries"]==v["profile"] for v in counts.values()),counts)
    e.check("G4.source_unchanged",source_before==SCENES([batch]) and before==sources(normal))
    return {"fixture_label":"PROTOCOL_TEST_FIXTURE_ONLY","fixture_sha256":sha(fixture),"counts":counts,"new_receiver_calls":0,
        "not_executed":{name:{"count":None,"reason":"outside TASK-033; not reported as guarded zero"} for name in
            ("human_initial_judgment","AI","new_junction","historical_suites")}}

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument("--out-dir",required=True);parser.add_argument("--replay")
    parser.add_argument("--mutate",choices=("none","candidate-return","ledger-late","checks-late"),default="none")
    args=parser.parse_args(argv);out=Path(args.out_dir).resolve()
    if not out.is_relative_to(TEST_ROOT.resolve()) or out==TEST_ROOT.resolve() or out.exists() or not out.name.startswith("task033_"):
        raise SystemExit("out-dir must be never-existing task033_ strict descendant")
    e=evidence_module();e.ROUND["id"]=out.name;out.mkdir(parents=True,exist_ok=False);obs=None
    if args.replay:
        source=Path(args.replay).resolve()
        if not source.is_relative_to(TEST_ROOT.resolve()) or source==out: raise SystemExit("invalid replay source")
        checkpoint=json.loads((source/"expected_observations.json").read_bytes());extra={"replay_only":True,"new_business_calls":0,"source":str(source)}
    else:
        if args.mutate!="none": raise SystemExit("mutations require replay")
        rt=load(ROOT/"scripts/runtime_gate1.py","task033_runtime_under_test");obs=Observer(rt,e);sys.setprofile(obs.profile)
        try: extra=run(e,rt,obs,out)
        finally: sys.setprofile(None)
        checkpoint=e.freeze_expectations()
    original_read,injection=Path.read_bytes,{"hits":0}
    if args.mutate in ("ledger-late","checks-late"):
        def read_then_mutate(path):
            result=original_read(path);frame=sys._getframe(1)
            if frame.f_code is e.finish.__code__ and "terminal_buffers" in frame.f_locals and path==out/"expected_observations.json" and not injection["hits"]:
                target=out/("file_ledger.json" if args.mutate=="ledger-late" else "checks.json");before=original_read(target)
                with open(target,"ab") as stream: stream.write(b"\n")
                injection.update(hits=1,target=target.name,before_size=len(before),after_size=len(before)+1,before_sha256=sha(before),
                    after_sha256=sha(before+b"\n"),boundary="after_semantic_ledger_consumption_in_terminal_byte_loop")
            return result
        Path.read_bytes=read_then_mutate
    try: code=e.finish(out,checkpoint,"candidate-return" if args.mutate=="candidate-return" else "none",obs,extra)
    finally: Path.read_bytes=original_read
    if args.mutate in ("ledger-late","checks-late"): (out/"control_observation.json").write_bytes(canon(injection)+b"\n")
    return code

if __name__=="__main__": raise SystemExit(main())
