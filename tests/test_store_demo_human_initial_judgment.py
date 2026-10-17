"""TASK-036 bounded storage tests; accepted short evidence closure reused read-only."""
from __future__ import annotations
import argparse
import builtins
import copy
from contextlib import contextmanager
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
TEST_ROOT=ROOT/'data/human_initial_judgment_store_tests'
RECORDS_ROOT=ROOT/'data/human_initial_judgment_records'
STORE_PATH=ROOT/'scripts/store_demo_human_initial_judgment.py'
SOURCE=ROOT/'data/human_initial_judgment_tests/task035_r1_run_02/technical_base.json'
def canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def sha(v):return hashlib.sha256(v).hexdigest()
def fp(v):return sha(canon(v))
def read(p):return json.loads(p.read_bytes())
def put(p,v):
    with p.open('xb') as f:f.write(canon(v)+b'\n')
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def scene(path,record_root):
    if not path.is_absolute():path=Path.cwd()/path
    if not path.is_relative_to(record_root):return {'path':str(path),'availability':'not_available','reason':'outside this test round; no enumeration'}
    if not path.exists():return {'path':str(path),'exists':False}
    if not path.is_dir():return {'path':str(path),'exists':True,'kind':'file','sha256':sha(path.read_bytes())}
    files={};names=sorted(x.name for x in path.iterdir())
    for name in names[:16]:
        item=path/name
        if item.is_file():
            raw=item.read_bytes();files[name]={'byte_size':len(raw),'sha256':sha(raw)}
        else:files[name]={'kind':'directory_or_other'}
    return {'path':str(path),'exists':True,'names':names,'files':files,'enumeration_bound':16}

class Observer:
    def __init__(self,module,e,old,record_root):
        self.e,self.old,self.record_root=e,old,record_root
        self.count=0;self.api={name:0 for name in ('save_human_initial_judgment_snapshots','verify_human_initial_judgment_snapshots')}
        self.normalizer=self.loader=None;self._other={};self.core_codes=set();self.public_codes={getattr(module,k).__code__:k for k in self.api}
        self.native={};self.public_points={};self.guard_hits=[];self.probe_hits=[];self.io_events=[]
        self.private_raw_code=module._reject_chain.__code__;self.private_control_active=False;self.private_control_entries=0
        real=module._load_core
        def observed_load(captures):
            core=real(captures);original=core.build_human_initial_judgment_record;self.core_codes.add(original.__code__)
            def observed_core(*args,**kwargs):
                cid=e.CALL_STACK[-1];nid=f'core_{len(e.CORE_RECORDS)+1:04d}'
                refs=[*args[:3],kwargs.get('prior_history')];e.CORE_INPUT_REFS[nid]=refs
                row={'nested_id':nid,'core':'human_initial_judgment','caller_api':cid,
                    'args':old.evidence_value(args),'kwargs':old.evidence_value(kwargs),'input_refs_before':old.input_points(refs)}
                try:
                    result=original(*args,**kwargs);row.update(outcome='returned',**{'return':copy.deepcopy(result)});return result
                except Exception as exc:
                    row.update(outcome='exception',exception_type=type(exc).__name__,exception_str=str(exc),
                        field=getattr(exc,'field',None),stage=getattr(exc,'stage',None),reasons=copy.deepcopy(getattr(exc,'reasons',None)),
                        traceback=traceback.format_exc(),cause_chain=e.chain_of(exc));raise
                finally:row['input_refs_after']=old.input_points(refs);e.CORE_RECORDS.append(row)
            core.build_human_initial_judgment_record=observed_core;return core
        module._load_core=observed_load
    def profile(self,frame,event,arg):
        if event!='call':return
        if self.private_control_active and frame.f_code is self.private_raw_code:self.private_control_entries+=1
        if frame.f_code in self.public_codes:self.api[self.public_codes[frame.f_code]]+=1
        elif frame.f_code in self.core_codes:self.count+=1
        elif str(Path(frame.f_code.co_filename).absolute()).startswith(str(ROOT/'scripts')) and frame.f_code.co_flags & 1 \
                and frame.f_code.co_name.isidentifier() and not frame.f_code.co_name.startswith('_'):
            self._other[frame.f_code.co_name]=self._other.get(frame.f_code.co_name,0)+1
    @contextmanager
    def guard(self,module,clock=False,prove=False):
        original_socket,original_popen=socket.socket,subprocess.Popen
        original_open,original_io=builtins.open,io.open
        def deny(kind):
            def fn(*a,**k):
                (self.probe_hits if prove else self.guard_hits).append(kind)
                raise AssertionError('TASK036 forbidden '+kind)
            return fn
        def opened(real):
            def fn(path,mode='r',*args,**kwargs):
                p=Path(path).absolute();writing=any(x in mode for x in 'wax+')
                allowed=p.is_relative_to(self.record_root) if writing else (p.is_relative_to(self.record_root) or p in set(module.COMPONENT_PATHS.values()))
                if writing and clock:allowed=False  # verify is strictly read-only, even for identical bytes
                if not allowed:self.guard_hits.append('write' if writing else 'read');raise AssertionError('TASK036 out of scope I/O '+str(p))
                self.io_events.append({'path':str(p),'mode':mode,'writing':writing,
                    'call_id':self.e.CALL_STACK[-1] if self.e.CALL_STACK else None});return real(path,mode,*args,**kwargs)
            return fn
        original_datetime=module.datetime
        class NoNow(original_datetime):
            @classmethod
            def now(cls,*a,**k):return deny('verify_clock')()
        try:
            socket.socket=deny('network');subprocess.Popen=deny('subprocess')
            builtins.open=opened(original_open);io.open=opened(original_io)
            if clock:module.datetime=NoNow
            yield
        finally:
            socket.socket,subprocess.Popen=original_socket,original_popen
            builtins.open,io.open=original_open,original_io;module.datetime=original_datetime

def run(e,old,out):
    record_root=RECORDS_ROOT/out.name
    if record_root.exists():raise RuntimeError('record test root must never exist')
    record_root.mkdir(parents=True,exist_ok=False)
    module=load(STORE_PATH,'task036_store_under_test');observer=Observer(module,e,old,record_root)
    # Observation describes real path inputs as bounded scenes; illegal in-memory
    # candidates use the accepted reversible evidence encoding, never as core data.
    def describe(v):
        if isinstance(v,Path):return scene(v,record_root)
        if type(v) in (list,tuple):return [describe(x) for x in v]
        if type(v) is dict:return {k:describe(x) for k,x in v.items()}
        return old.evidence_value(v)
    e.jsonable=describe;e.core_input_point=old.input_points
    fixture=read(SOURCE);base=[fixture[k] for k in ('submission','materials','expectations','prior_history')]
    sources=[SOURCE,ROOT/'data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json',
        ROOT/'data/human_initial_judgment_tests/task035_setup_01/human_fixture_supplement_02.json',
        ROOT/'data/human_initial_judgment_tests/task035_setup_01/human_fixture_supplement_03.json']
    source_ids={}
    for path in sources:
        raw=path.read_bytes();source_ids[path.relative_to(ROOT).as_posix()]={'sha256':sha(raw),'byte_size':len(raw)}
        with (out/(path.name+'.source.bin')).open('xb') as f:f.write(raw)
    def invoke(label,operation,*args,field=None,error_stage=None,core_count=None,**kwargs):
        before_core=observer.count;before_public=sum(observer.api.values())
        refs=[*args[:3],kwargs.get('prior_history')] if operation=='save' else []
        before_points=old.input_points(refs);path=kwargs['out_dir'] if operation=='save' else args[0]
        before_scene=scene(path,record_root);after_points=[];after_scene=[]
        real=getattr(module,'save_human_initial_judgment_snapshots' if operation=='save' else 'verify_human_initial_judgment_snapshots')
        native=[]
        def called(*a,**kw):
            try:
                with observer.guard(module,clock=operation=='verify'):
                    value=real(*a,**kw);native.append(value);return value
            finally:
                # Immediate public return/exception, after the I/O guard has been
                # restored; test scene reads are not production read events.
                after_points.extend(old.input_points(refs));after_scene.append(scene(path,record_root))
        err,result,cid=e.call_api(module,label,called,*args,**kwargs)
        end_points=old.input_points(refs)
        e.API_RECORDS[-1].update(record_category='store_public',actual_core_delta=observer.count-before_core,
            actual_public_delta=sum(observer.api.values())-before_public,reasons=copy.deepcopy(getattr(err,'reasons',None)),
            public_inputs_before=before_points,public_inputs_after=after_points,public_inputs_api_end=end_points,
            path_role='output' if operation=='save' else 'input',path_scene_before=before_scene,
            path_scene_after=after_scene[0],path_scene_api_end=scene(path,record_root),secondary_errors=getattr(err,'secondary_errors',None))
        if native:observer.native[cid]=native[0]
        ok=(isinstance(err,module.HumanInitialJudgmentStoreBlocked) and err.field==field and bool(err.reason) and err.reasons==[err.reason]) if field else (
            isinstance(err,module.HumanInitialJudgmentStoreError) and err.stage==error_stage if error_stage else err is None)
        ok=ok and (core_count is None or observer.count-before_core==core_count)
        e.check(label,ok,{'call_id':cid,'field':getattr(err,'field',None),'stage':getattr(err,'stage',None),'core_delta':observer.count-before_core,'type':type(err).__name__})
        return err,result,cid
    def save(label,leaf,values=None,**opts):
        v=copy.deepcopy(base) if values is None else values
        return invoke(label,'save',*v[:3],prior_history=v[3],out_dir=leaf,**opts)
    def clone(name,omit=()):
        leaf=record_root/name;leaf.mkdir()
        for file in module.FILES:
            if file in omit:continue
            with (leaf/file).open('xb') as f:f.write((normal/file).read_bytes())
        return leaf
    def rewrite(leaf,name,obj):
        (leaf/name).write_bytes(canon(obj)+b'\n')
    def patch_manifest(leaf,edit):
        obj=read(leaf/'manifest.json');edit(obj);rewrite(leaf,'manifest.json',obj)
    sys.setprofile(observer.profile)
    try:
        with observer.guard(module,clock=True,prove=True):
            for probe in (socket.socket,lambda:subprocess.Popen(['TASK036_MUST_NOT_START']),module.datetime.now):
                try:probe()
                except AssertionError:pass
        e.check('G7.guard_proof',observer.probe_hits==['network','subprocess','verify_clock'],observer.probe_hits)
        normal=record_root/'normal';normal_inputs=copy.deepcopy(base)
        registrations=[];real_registration=module._registration
        def observed_registration():
            value=real_registration();registrations.append(copy.deepcopy(value));return value
        module._registration=observed_registration
        try:_,saved,saved_id=save('G1.save',normal,normal_inputs,core_count=1)
        finally:module._registration=real_registration
        _,verified,_=invoke('G1.verify','verify',normal,core_count=1)
        verify_row=e.API_RECORDS[-1]
        e.check('G1.verify_path_unchanged',canon(verify_row['path_scene_before'])==canon(verify_row['path_scene_after'])==canon(verify_row['path_scene_api_end']))
        expected=old.expected_return(base)
        e.check('G1.complete_return',canon(saved['judgment_result'])==canon(expected)==canon(read(normal/'judgment_result.json'))
            and len(saved)==len(verified)==11 and len(saved['files'])==6 and saved['snapshots']==dict(zip(('submission','materials','expectations','prior_history'),base)))
        e.check('G1.boundaries_time',all(type(x) is bool and x is False for x in saved['boundaries'].values())
            and all(x is False for x in saved['judgment_result']['record']['boundaries'].values())
            and saved['technical_registration']==verified['technical_registration']
            and saved['snapshots']['submission']['decided_at_raw']=='2026-10-16')
        objects=dict(zip(('submission.json','materials.json','expectations.json','prior_history.json'),copy.deepcopy(base)))
        objects['judgment_result.json']=expected
        raw_buffers={name:canon(value)+b'\n' for name,value in objects.items()}
        binding_paths={
            'core_file_sha256':ROOT/'scripts/build_demo_human_initial_judgment.py','store_file_sha256':STORE_PATH,
            'protocol_file_sha256':ROOT/'docs/proposals/HUMAN_INITIAL_JUDGMENT_PROTOCOL_V1_DRAFT.md',
            'cases_file_sha256':ROOT/'docs/proposals/HUMAN_INITIAL_JUDGMENT_CASES_V1_DRAFT.md',
            'contract_file_sha256':ROOT/'docs/AUDIT_CONTRACT.md',
            'contract_effective_record_file_sha256':ROOT/'docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md'}
        def independent_entry(name):
            return {'relative':name,'byte_size':len(raw_buffers[name]),'file_sha256':sha(raw_buffers[name]),'object_fingerprint':fp(objects[name])}
        manifest={'manifest_version':'TASK-036-human-initial-judgment-store-manifest-1.0','store_status':'HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_STORED',
            'scope':'STORED_SNAPSHOTS_ONLY','identity':{'batch_id':base[0]['batch_id'],'event_id':base[0]['event_id'],'request_id':base[0]['request_binding']['request_id']},
            'component_bindings':{k:sha(p.read_bytes()) for k,p in binding_paths.items()},
            'fingerprints':{'submission_fingerprint':fp(base[0]),'materials_snapshot_fingerprint':fp(base[1]),
                'materials_body_fingerprint':fp({k:v for k,v in base[1].items() if k!='materials_fingerprint'}),
                'expectations_fingerprint':fp(base[2]),'prior_history_fingerprint':fp(base[3]),'record_fingerprint':fp(expected['record']),
                'binding_fingerprint':fp(expected['record']['binding'])},
            'payloads':[independent_entry(name) for name in sorted(objects)],'technical_registration':registrations[0],
            'boundaries':{k:False for k in ('workflow_connected','execution_allowed','next_step_allowed','ai_enabled','identity_authenticated',
                'source_authenticity_proven','audit_conclusion_formed','final_judgment_recorded','complete_history_verified')}}
        objects['manifest.json']=manifest;raw_buffers['manifest.json']=canon(manifest)+b'\n'
        full={'status':'HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_STORED','scope':'STORED_SNAPSHOTS_ONLY','identity':manifest['identity'],
            'record_fingerprint':fp(expected['record']),'manifest_file_sha256':sha(raw_buffers['manifest.json']),
            'technical_registration':registrations[0],'component_bindings':manifest['component_bindings'],
            'files':[independent_entry(name) for name in sorted(objects)],'boundaries':manifest['boundaries'],
            'snapshots':dict(zip(('submission','materials','expectations','prior_history'),base)),'judgment_result':expected}
        verify_expected=copy.deepcopy(full);verify_expected['status']='HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_VERIFIED'
        e.check('G1.independent_full_store_return',len(registrations)==1 and canon(full)==canon(saved) and canon(verify_expected)==canon(verified)
            and all((normal/name).read_bytes()==raw for name,raw in raw_buffers.items()))
        put(out/'independent_normal_expectation.json',{'source':'fixed four inputs, independently constructed core record, measured real technical-time return, independent source bytes',
            'manifest':manifest,'save_result':full,'verify_result':verify_expected})
        before=canon(normal_inputs);observer.native[saved_id]['snapshots']['submission']['actor']['actor_id']='RETURN_MUTATION'
        observer.native[saved_id]['judgment_result']['record']['binding']['files'][0]['byte_size']=999999
        e.check('G1.native_return_no_alias',canon(normal_inputs)==before and read(normal/'submission.json')['actor']['actor_id']=='1')
        alternate=copy.deepcopy(base);alternate[0].update(read(sources[2])['human_values'])
        _,r,_=save('G1.uncertain',record_root/'uncertain',alternate,core_count=1)
        e.check('G1.uncertain_raw',r['snapshots']['submission']['reason']=='原始凭证缺失')
        alternate=copy.deepcopy(base);alternate[0]['reason']=read(sources[3])['human_values']['reason']
        save('G1.instruction_text',record_root/'text',alternate,core_count=1)
        for name,edit,field in (
            ('entity_bytes',lambda v:v[1]['entity'].__setitem__('company',b'bad-company'),'materials.entity.company'),
            ('wrong_request',lambda v:v[0]['request_binding'].__setitem__('request_id','TECHNICAL-WRONG'),'submission.request_binding.request_id'),
            ('history_none',lambda v:v.__setitem__(3,None),'prior_history')):
            v=copy.deepcopy(base);edit(v);leaf=record_root/name
            err,_,_=save('G2.'+name,leaf,v,field=field,core_count=1)
            e.check('G2.no_leaf.'+name,not leaf.exists() and type(err.__cause__).__name__=='HumanInitialJudgmentBlocked')
        component_controls=[];injection_open=io.open
        for key in ('core_file_sha256','contract_file_sha256'):
            real_path=module.COMPONENT_PATHS[key];copy_path=out/(key+'.copy.bin');copy_path.write_bytes(real_path.read_bytes())
            original_loader=module._load_core;module.COMPONENT_PATHS[key]=copy_path;hit=[0]
            def late_component(captures):
                loaded=original_loader(captures)
                # Explicit test-owned mutation, separately recorded; production
                # writes remain restricted to its records root by the real guard.
                with injection_open(copy_path,'ab') as f:f.write(b'\n')
                hit[0]+=1;return loaded
            module._load_core=late_component;leaf=record_root/('precore_'+key)
            try:save('G2.precore_'+key,leaf,field='component_bindings.'+key,core_count=0)
            finally:module.COMPONENT_PATHS[key]=real_path;module._load_core=original_loader
            e.check('G2.precore_no_leaf_'+key,hit==[1] and not leaf.exists())
            component_controls.append({'key':key,'path':str(copy_path),'hits':hit[0],'actor':'TEST_CONTROL_INJECTION',
                'file_sha256_after':sha(copy_path.read_bytes()),'original_source_unchanged':sha(real_path.read_bytes())==module.FROZEN[key]})
        put(out/'precore_controls.json',component_controls)
        original_loader=module._load_core
        def internal_error(captures):
            loaded=original_loader(captures);real_canonical=loaded._canonical
            def fail_record(value):
                if type(value) is dict and 'record_version' in value:raise ValueError('TASK036_CONTROLLED_CORE_ERROR')
                return real_canonical(value)
            loaded._canonical=fail_record;return loaded
        module._load_core=internal_error;leaf=record_root/'core_error'
        try:err,_,_=save('G2.core_error',leaf,error_stage='internal',core_count=1)
        finally:module._load_core=original_loader
        e.check('G2.core_error_chain',not leaf.exists() and 'HumanInitialJudgmentError' in ' '.join(e.chain_of(err)) and 'ValueError' in ' '.join(e.chain_of(err)))
        empty=record_root/'empty';empty.mkdir()
        for label,path in (('root',RECORDS_ROOT),('outside',out/'outside'),('empty',empty),('existing',normal)):
            snapshot=scene(path,record_root);save('G3.'+label,path,field='out_dir',core_count=0)
            e.check('G3.unchanged.'+label,scene(path,record_root)==snapshot)
        put(out/'junction_probe.json',{'executed_reparse_control':None,
            'not_executed_reason':'TASK-036-R1: prior OS permission refusal retained; physical junction not retried',
            'prior_read_only_evidence':'data/human_initial_judgment_store_tests/task036_run_03/junction_probe.json'})
        # Use the real lstat result on a normal, new directory; the synthetic
        # reparse attribute is a metadata control, not a physical junction.
        alias=record_root/'raw_alias';alias.mkdir();real_lstat=Path.lstat;raw_controls=[]
        for operation in ('save','verify'):
            for relative in (False,True):
                target=normal if operation=='verify' else record_root/f'raw_save_{relative}'
                raw_path=alias/'..'/target.name
                if relative:raw_path=raw_path.relative_to(Path.cwd())
                hits=[]
                def synthetic_lstat(path,*a,**k):
                    actual=real_lstat(path,*a,**k)
                    if path==alias:
                        hits.append(str(path))
                        return SimpleNamespace(st_mode=actual.st_mode,st_file_attributes=getattr(actual,'st_file_attributes',0)|0x400)
                    return actual
                Path.lstat=synthetic_lstat
                try:
                    if operation=='save':err,_,cid=save(f'R1.raw_save.{relative}',raw_path,field='out_dir',core_count=0)
                    else:err,_,cid=invoke(f'R1.raw_verify.{relative}','verify',raw_path,field='record_dir',core_count=0)
                finally:Path.lstat=real_lstat
                e.check(f'R1.raw_consumed.{operation}.{relative}',len(hits)==1 and (operation=='verify' or not target.exists()))
                raw_controls.append({'call_id':cid,'operation':operation,'relative_input':relative,'raw_path':str(raw_path),
                    'parts':list(raw_path.parts),'alias_lstat_hits':len(hits),'field':err.field,'synthetic_metadata_only':True})
        Path.lstat=synthetic_lstat;hits=[];private_public_before=sum(observer.api.values());private_core_before=observer.count
        observer.private_control_active=True
        try:
            try:module._reject_chain(alias/'..'/normal.name,'record_dir')
            except module.HumanInitialJudgmentStoreBlocked as err:
                private_control={'field':err.field,'reason':err.reason,'alias_lstat_hits':len(hits),
                    'public_API_entries':sum(observer.api.values())-private_public_before,'core_entries':observer.count-private_core_before,
                    'private_code_entries':observer.private_control_entries}
            else:raise AssertionError('raw helper control must reject')
        finally:Path.lstat=real_lstat;observer.private_control_active=False
        e.check('R1.private_raw_chain',private_control['field']=='record_dir' and private_control['alias_lstat_hits']==1
            and private_control['private_code_entries']==1 and private_control['public_API_entries']==private_control['core_entries']==0)
        relative_normal=record_root/'relative_normal';relative_input=Path(os.path.relpath(relative_normal,Path.cwd()))
        _,relative_saved,_=save('R1.normal_relative_save',relative_input,core_count=1)
        _,relative_verified,_=invoke('R1.normal_relative_verify','verify',relative_input,core_count=1)
        e.check('R1.normal_relative_return',canon(relative_saved['judgment_result'])==canon(expected)==canon(relative_verified['judgment_result']))
        put(out/'raw_path_controls.json',{'public_controls':raw_controls,'private_control':private_control,
            'private_control_count':1,'physical_junction_executed':None,'relative_normal_success':True})
        # Genuine exclusive stream, not a replacement of the production writer.
        half=record_root/'half';real_open=Path.open;writer={'hits':0,'mode':None}
        class HalfStream:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):self.stream.__enter__();return self
            def __exit__(self,*a):return self.stream.__exit__(*a)
            def write(self,data):
                n=len(data)//2;self.stream.write(data[:n]);self.stream.flush();writer.update(hits=writer['hits']+1,written=n,total=len(data));raise OSError('TASK036_REAL_HALF_WRITE')
        def opened(path,mode='r',*a,**k):
            stream=real_open(path,mode,*a,**k)
            if path==half/'expectations.json' and mode=='xb':writer['mode']=mode;return HalfStream(stream)
            return stream
        Path.open=opened
        try:err,_,_=save('G4.real_half',half,error_stage='write.expectations.json',core_count=1)
        finally:Path.open=real_open
        e.check('G4.half_real_bytes',writer['hits']==1 and writer['mode']=='xb' and (half/'expectations.json').stat().st_size==writer['written']
            and 'OSError' in ' '.join(e.chain_of(err)) and len(read(half/'failure.json'))==10,writer)
        put(out/'writer_control.json',writer)
        snapshot=scene(half,record_root);invoke('G4.failure_first','verify',half,field='failure.json',core_count=0)
        e.check('G4.verify_no_write',scene(half,record_root)==snapshot)
        save('G4.failed_existing',half,field='out_dir',core_count=0)
        double=record_root/'double_failure';counters={'primary':0,'secondary':0}
        class FaultStream:
            def __init__(self,stream,secondary):self.stream,self.secondary=stream,secondary
            def __enter__(self):self.stream.__enter__();return self
            def __exit__(self,*a):return self.stream.__exit__(*a)
            def write(self,data):
                key='secondary' if self.secondary else 'primary';counters[key]+=1
                if not self.secondary:self.stream.write(data[:len(data)//2]);self.stream.flush()
                raise OSError('TASK036_'+key.upper()+'_WRITE_ERROR')
        def double_open(path,mode='r',*a,**k):
            stream=real_open(path,mode,*a,**k)
            if mode=='xb' and path in (double/'expectations.json',double/'failure.json'):
                return FaultStream(stream,path.name=='failure.json')
            return stream
        Path.open=double_open
        try:err,_,_=save('G4.primary_and_secondary',double,error_stage='write.expectations.json',core_count=1)
        finally:Path.open=real_open
        e.check('G4.secondary_preserved',counters=={'primary':1,'secondary':1} and bool(err.secondary_errors)
            and 'PRIMARY_WRITE_ERROR' in ' '.join(e.chain_of(err)) and 'SECONDARY_WRITE_ERROR' in str(err)
            and (double/'failure.json').stat().st_size==0,counters)
        invoke('G4.partial_failure_rejected','verify',double,field='failure.json',core_count=0)
        # The first real registration belongs to the manifest; fail only the
        # diagnostic registration after a genuine exclusive-stream half-write.
        clock_leaf=record_root/'diagnostic_clock';clock={'registrations':0,'writes':0,'mode':None,'real_first_registration':None}
        registration=module._registration
        class ClockHalfStream:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):self.stream.__enter__();return self
            def __exit__(self,*a):return self.stream.__exit__(*a)
            def write(self,data):
                n=len(data)//2;self.stream.write(data[:n]);self.stream.flush()
                clock.update(writes=clock['writes']+1,written=n,total=len(data))
                raise OSError('TASK036_R1_REAL_HALF_WRITE')
        def clock_open(path,mode='r',*a,**k):
            stream=real_open(path,mode,*a,**k)
            if path==clock_leaf/'expectations.json' and mode=='xb':clock['mode']=mode;return ClockHalfStream(stream)
            return stream
        def clock_registration():
            clock['registrations']+=1
            if clock['registrations']==2:raise OSError('TASK036_R1_DIAGNOSTIC_CLOCK_ERROR')
            value=registration();clock['real_first_registration']=copy.deepcopy(value);return value
        Path.open=clock_open;module._registration=clock_registration
        try:err,_,cid=save('R1.diagnostic_clock',clock_leaf,error_stage='write.expectations.json',core_count=1)
        finally:Path.open=real_open;module._registration=registration
        e.check('R1.primary_survives_clock',clock['registrations']==2 and clock['writes']==1 and clock['mode']=='xb'
            and err.reason=='TASK036_R1_REAL_HALF_WRITE' and err.reasons==[err.reason]
            and type(err.__cause__) is OSError and str(err.__cause__)==err.reason
            and any(x['exception_type']=='OSError' and x['message']=='TASK036_R1_DIAGNOSTIC_CLOCK_ERROR' for x in err.secondary_errors)
            and not (clock_leaf/'failure.json').exists() and (clock_leaf/'expectations.json').stat().st_size==clock['written'],clock)
        before_clock_verify=scene(clock_leaf,record_root)
        invoke('R1.incomplete_after_clock','verify',clock_leaf,field='files',core_count=0)
        e.check('R1.clock_incomplete_readonly',scene(clock_leaf,record_root)==before_clock_verify)
        put(out/'diagnostic_clock_control.json',{'call_id':cid,'control':clock,'top_exception':type(err).__name__,
            'stage':err.stage,'primary_reason':err.reason,'cause_chain':e.chain_of(err),'secondary_errors':err.secondary_errors,
            'failure_created':False,'test_injection':True})
        bad_failure=clone('bad_failure');rewrite(bad_failure,'failure.json',[])
        invoke('G4.invalid_failure','verify',bad_failure,field='failure.json',core_count=0)
        variants=(
            ('missing',lambda p:None,'files'),
            ('unknown',lambda p:put(p/'unknown.json',{}),'files'),
            ('directory',lambda p:(p/'subdir').mkdir(),'files'),
            ('size_float',lambda p:patch_manifest(p,lambda m:m['payloads'][0].__setitem__('byte_size',float(m['payloads'][0]['byte_size']))),'manifest.payloads[0].byte_size'),
            ('false_integer',lambda p:patch_manifest(p,lambda m:m['boundaries'].__setitem__('ai_enabled',0)),'manifest.boundaries.ai_enabled'),
            ('hash_LF',lambda p:patch_manifest(p,lambda m:m['fingerprints'].__setitem__('record_fingerprint',m['fingerprints']['record_fingerprint']+'\n')),'manifest.fingerprints.record_fingerprint'),
            ('file_FP_swap',lambda p:patch_manifest(p,lambda m:m['payloads'][0].__setitem__('file_sha256',m['payloads'][0]['object_fingerprint'])),'manifest.payloads[0]'),
            ('identity',lambda p:patch_manifest(p,lambda m:m['identity'].__setitem__('batch_id','TECHNICAL-OTHER')),'manifest.identity'),
            ('component',lambda p:patch_manifest(p,lambda m:m['component_bindings'].__setitem__('core_file_sha256','0'*64)),'manifest.component_bindings'))
        for name,edit,field in variants:
            leaf=clone(name,omit=('materials.json',) if name=='missing' else ());edit(leaf);snapshot=scene(leaf,record_root)
            invoke('G5.'+name,'verify',leaf,field=field,core_count=0)
            e.check('G5.read_only.'+name,scene(leaf,record_root)==snapshot)
        leaf=clone('self_consistent_wrong_result');judgment=read(leaf/'judgment_result.json')
        judgment['record']['human_initial_judgment']['reason']='TECHNICAL-NEGATIVE-REPLACEMENT'
        judgment['record_fingerprint']=fp(judgment['record']);rewrite(leaf,'judgment_result.json',judgment)
        manifest=read(leaf/'manifest.json');manifest['fingerprints']['record_fingerprint']=fp(judgment['record'])
        entry=next(x for x in manifest['payloads'] if x['relative']=='judgment_result.json');raw=(leaf/'judgment_result.json').read_bytes()
        entry.update(byte_size=len(raw),file_sha256=sha(raw),object_fingerprint=fp(judgment));rewrite(leaf,'manifest.json',manifest)
        invoke('G5.full_core_recomputation','verify',leaf,field='judgment_result',core_count=1)
        late=clone('late_verify');original_return=module._build_return;hit=[0];original_bytes=(late/'judgment_result.json').read_bytes()
        def build_late(*a,**k):
            returned=original_return(*a,**k)
            with injection_open(late/'judgment_result.json','ab') as f:f.write(b'\n')
            hit[0]+=1;return returned
        module._build_return=build_late
        try:invoke('G6.verify_late','verify',late,field='judgment_result.json',core_count=1)
        finally:module._build_return=original_return
        e.check('G6.once_and_no_failure',hit==[1] and not (late/'failure.json').exists())
        invoke('G6.retained_bad','verify',late,field='judgment_result.json',core_count=0)
        with (out/'late_judgment_result.bad.bin').open('xb') as f:f.write((late/'judgment_result.json').read_bytes())
        (late/'judgment_result.json').write_bytes(original_bytes)
        invoke('G6.own_exact_restore','verify',late,core_count=1)
        late_save=record_root/'late_save';hit=[0]
        def build_late_save(*a,**k):
            returned=original_return(*a,**k)
            with injection_open(late_save/'submission.json','ab') as f:f.write(b'\n')
            hit[0]+=1;return returned
        module._build_return=build_late_save
        try:save('G6.save_late',late_save,field='submission.json',core_count=1)
        finally:module._build_return=original_return
        e.check('G6.save_failure',hit==[1] and len(read(late_save/'failure.json'))==10)
        put(out/'late_controls.json',{'actor':'TEST_CONTROL_INJECTION','write_entry':'captured real io.open, outside production I/O guard',
            'verify_target':str(late/'judgment_result.json'),'bad_verify_bytes_preserved_at':str(out/'late_judgment_result.bad.bin'),
            'verify_original_sha256':sha(original_bytes),'verify_bad_sha256':sha((out/'late_judgment_result.bad.bin').read_bytes()),
            'verify_exact_own_restore':(late/'judgment_result.json').read_bytes()==original_bytes,
            'save_target':str(late_save/'submission.json'),'save_hits':hit[0]})
        e.check('G7.real_count_closure',sum(observer.api.values())==len(e.API_RECORDS)
            and observer.count==len(e.CORE_RECORDS)==sum(x['actual_core_delta'] for x in e.API_RECORDS),{'public':observer.api,'core':observer.count})
        e.check('G7.input_three_points',all(canon(x['input_refs_before'])==canon(x['input_refs_after'])==canon(x['input_refs_api_end']) for x in e.CORE_RECORDS)
            and all(canon(x['public_inputs_before'])==canon(x['public_inputs_after'])==canon(x['public_inputs_api_end']) for x in e.API_RECORDS))
        e.check('G7.scope_guard',not observer.guard_hits and not observer._other,{'guard_hits':observer.guard_hits,'other':observer._other})
        put(out/'io_observations.json',{'events':observer.io_events,'guard_probes':observer.probe_hits,
            'guard_hits':observer.guard_hits,'actual_other_business_calls':observer._other})
    finally:sys.setprofile(None)
    for p,v in source_ids.items():assert sha((ROOT/p).read_bytes())==v['sha256']
    return observer,{'scope':'STORED_SNAPSHOTS_ONLY','registered_source_identities':source_ids,
        'actual_public_entry_counts':observer.api,'actual_nested_core_entries':observer.count,
        'complete_history_verified':False,'technical_projections_are_actual_Gate_verification':False,
        'not_executed':{'extra_positive_human_times':None,'workflow_and_other_business_cores':None},
        'not_executed_reason':'extra human time values not provided; workflow/upstream/history/AI outside scope'}

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--out-dir',required=True);parser.add_argument('--replay')
    parser.add_argument('--mutate',choices=('none','candidate-return','ledger-late','checks-late'),default='none')
    args=parser.parse_args(argv);out=Path(args.out_dir).resolve()
    if out==TEST_ROOT.resolve() or not out.is_relative_to(TEST_ROOT.resolve()) or out.exists() or not out.name.startswith('task036_'):
        raise SystemExit('out-dir must be a never-existing task036_ strict descendant')
    old=load(ROOT/'tests/test_build_demo_human_initial_judgment.py','task036_readonly_observation_helpers');e=old.evidence_module()
    original_build=e.build_candidate
    def build(*a,**k):
        c=original_build(*a,**k);c['summary']['task']='TASK-036';c['summary']['scope']='STORED_SNAPSHOTS_ONLY'
        c['summary']['record_categories']={'store_public':len(c['api_records']),'nested_core':len(c['core_records'])}
        c['summary']['observed']={'store_public_entries':a[1].api if a[1] else None,'core_entries':a[1].count if a[1] else None,
            'replayed_records_are_new_calls':False if a[1] is None else None}
        return c
    e.build_candidate=build;e.ROUND['id']=out.name;out.mkdir(parents=True,exist_ok=False)
    if args.replay:
        source=Path(args.replay).resolve()
        if not source.is_relative_to(TEST_ROOT.resolve()) or not source.name.startswith('task036_') or source==out:raise SystemExit('invalid replay source')
        checkpoint=read(source/'expected_observations.json');observer=None;extra={'replay_only':True,'source':str(source)}
    else:
        if args.mutate!='none':raise SystemExit('mutation requires replay')
        observer,extra=run(e,old,out);checkpoint=e.freeze_expectations()
    original_read=Path.read_bytes;injection={'hits':0}
    if args.mutate in ('ledger-late','checks-late'):
        def read_then_mutate(path):
            returned=original_read(path);frame=sys._getframe(1)
            if frame.f_code is e.finish.__code__ and 'terminal_buffers' in frame.f_locals and path==out/'expected_observations.json' and not injection['hits']:
                target=out/('file_ledger.json' if args.mutate=='ledger-late' else 'checks.json');before=original_read(target)
                with target.open('ab') as f:f.write(b'\n')
                injection.update(hits=1,target=target.name,before_size=len(before),after_size=len(before)+1,before_sha256=sha(before),after_sha256=sha(before+b'\n'))
            return returned
        Path.read_bytes=read_then_mutate
    try:code=e.finish(out,checkpoint,'candidate-return' if args.mutate=='candidate-return' else 'none',observer,extra)
    finally:Path.read_bytes=original_read
    if args.mutate in ('ledger-late','checks-late'):put(out/'control_observation.json',injection)
    return code
if __name__=='__main__':raise SystemExit(main())
