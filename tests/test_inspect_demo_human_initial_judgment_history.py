"""TASK-037 finite namespace tests; accepted short closure reused read-only."""
from __future__ import annotations
import argparse,builtins,copy,datetime,hashlib,importlib.util,io,json,os,socket,subprocess,sys,traceback
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
TEST_ROOT=ROOT/'data/human_initial_judgment_history_tests';RECORD_ROOT=ROOT/'data/human_initial_judgment_records'
HISTORY=ROOT/'scripts/inspect_demo_human_initial_judgment_history.py'
STORE=ROOT/'scripts/store_demo_human_initial_judgment.py'
SOURCE=ROOT/'data/human_initial_judgment_tests/task035_r1_run_02/technical_base.json'
HUMANS=(ROOT/'data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json',ROOT/'data/reviews/task036r1_gpt_20261016_193749/human_history_fixture_supplement.json')
SCOPE='TASK037-DECLARED-TECHNICAL-NAMESPACE'
def canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def sha(b):return hashlib.sha256(b).hexdigest()
def fp(v):return sha(canon(v))
def read(p):return json.loads(p.read_bytes())
def put(p,v):
    with p.open('xb') as f:f.write(canon(v)+b'\n')
def load(p,name):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def scene(p,root):
    p=Path.cwd()/p
    if not p.is_relative_to(root):return {'path':str(p),'available':False,'reason':'outside this round; not enumerated'}
    if not p.exists():return {'path':str(p),'exists':False}
    result={'path':str(p),'exists':True,'files':{}}
    def file(q):
        raw=q.read_bytes();return {'byte_size':len(raw),'sha256':sha(raw)}
    if not p.is_dir():result['files'][p.name]=file(p);return result
    for child in sorted(p.iterdir())[:32]:
        if child.is_file():result['files'][child.name]=file(child)
        elif child.is_dir():
            result['files'][child.name]={'directory':{q.name:file(q) if q.is_file() else {'other':True} for q in sorted(child.iterdir())[:16]}}
    return result

class Observer:
    def __init__(self,h,e,old,root):
        self.h,self.e,self.old,self.root=h,e,old,root;self.codes={};self.originals=[];self.modules=[]
        self.api={k:0 for k in ('history','setup_store_save','store_verify','pure_core')};self.count=0
        self.normalizer=self.loader=None;self._other={};self.guards=[];self.proof=[];self.io=[];self.layer_stack=[];self.serial=0
        self.register(h.inspect_human_initial_judgment_history,'history')
        real=h._load_store
        def observed_load():
            m,raw=real();self.instrument(m);return m,raw
        h._load_store=observed_load
    def register(self,fn,role):self.originals.append(fn);self.codes[id(fn.__code__)]=role
    def points(self,refs):
        rows=[]
        for v in refs:
            encoded={'$path':str(v)} if isinstance(v,Path) else self.old.evidence_value(copy.deepcopy(v))
            rows.append({'reference_id':id(v),'snapshot':encoded,'fingerprint':fp(encoded)})
        return rows
    def instrument(self,m):
        self.modules.append(m);self.register(m.save_human_initial_judgment_snapshots,'setup_store_save')
        verify=m.verify_human_initial_judgment_snapshots;self.register(verify,'store_verify')
        m.verify_human_initial_judgment_snapshots=self.wrap(verify,'store_verify')
        real=m._load_core
        def core_load(captures):
            core=real(captures);fn=core.build_human_initial_judgment_record;self.register(fn,'pure_core')
            core.build_human_initial_judgment_record=self.wrap(fn,'pure_core');return core
        m._load_core=core_load
    def wrap(self,fn,role):
        def called(*a,**k):
            self.serial+=1;nid=f'nested_{self.serial:04d}';cid=self.e.CALL_STACK[-1]
            refs=[*a[:3],k.get('prior_history')] if role=='pure_core' else list(a)
            self.e.CORE_INPUT_REFS[nid]=refs
            row={'nested_id':nid,'core':role,'caller_api':cid,'parent_nested_id':self.layer_stack[-1] if self.layer_stack else None,
                'args':self.e.jsonable(a),'kwargs':self.e.jsonable(k),'input_refs_before':self.points(refs)}
            if role=='store_verify':row['path_scene_before']=scene(a[0],self.root)
            self.layer_stack.append(nid)
            try:
                value=fn(*a,**k);row.update(outcome='returned',**{'return':copy.deepcopy(value)});return value
            except Exception as exc:
                row.update(outcome='exception',exception_type=type(exc).__name__,exception_str=str(exc),field=getattr(exc,'field',None),stage=getattr(exc,'stage',None),
                    reasons=copy.deepcopy(getattr(exc,'reasons',None)),traceback=traceback.format_exc(),cause_chain=self.e.chain_of(exc));raise
            finally:
                self.layer_stack.pop();row['input_refs_after']=self.points(refs)
                if role=='store_verify':row['path_scene_after']=scene(a[0],self.root)
                self.e.CORE_RECORDS.append(row)
        return called
    def profile(self,frame,event,arg):
        if event!='call':return
        role=self.codes.get(id(frame.f_code))
        if role:
            self.api[role]+=1
            if role in ('store_verify','pure_core'):self.count+=1
        elif str(Path(frame.f_code.co_filename).absolute()).startswith(str(ROOT/'scripts')) and frame.f_code.co_flags&1 and frame.f_code.co_name.isidentifier() and not frame.f_code.co_name.startswith('_'):
            self._other[frame.f_code.co_name]=self._other.get(frame.f_code.co_name,0)+1
    @contextmanager
    def guard(self,setup=False,prove=False):
        oldopen,oldio,oldos,oldsock,oldproc,olddt=builtins.open,io.open,os.open,socket.socket,subprocess.Popen,datetime.datetime
        mutators={name:getattr(os,name) for name in ('mkdir','unlink','remove','rmdir','rename','replace')}
        def deny(name):
            def no(*a,**k):(self.proof if prove else self.guards).append(name);raise AssertionError('TASK037_DENIED:'+name)
            return no
        def opened(fn):
            def call(path,mode='r',*a,**k):
                p=Path.cwd()/Path(path);writing=any(x in mode for x in 'wax+')
                allowed=(setup and p.is_relative_to(self.root)) if writing else (p.is_relative_to(self.root) or p in self.allowed_reads)
                if not allowed:return deny('write' if writing else 'read')()
                self.io.append({'path':str(p),'mode':mode,'writing':writing,'parent_call_id':self.e.CALL_STACK[-1] if self.e.CALL_STACK else None})
                return fn(path,mode,*a,**k)
            return call
        class NoNow(olddt):
            now=classmethod(deny('clock'));utcnow=classmethod(deny('clock'));today=classmethod(deny('clock'))
        saved_dates=[(m,m.datetime) for m in self.modules]
        try:
            builtins.open=opened(oldopen);io.open=opened(oldio);os.open=deny('os.open');socket.socket=deny('network');subprocess.Popen=deny('subprocess')
            if not setup:
                datetime.datetime=NoNow
                for m,_ in saved_dates:m.datetime=NoNow
                for name in mutators:setattr(os,name,deny('filesystem_mutation.'+name))
            yield
        finally:
            builtins.open,io.open,os.open,socket.socket,subprocess.Popen,datetime.datetime=oldopen,oldio,oldos,oldsock,oldproc,olddt
            for m,v in saved_dates:m.datetime=v
            for name,fn in mutators.items():setattr(os,name,fn)

def run(e,old,out):
    root=RECORD_ROOT/out.name;root.mkdir(parents=True,exist_ok=False)
    h=load(HISTORY,'task037_history_under_test');o=Observer(h,e,old,root)
    e.jsonable=lambda v:({'$path':str(v)} if isinstance(v,Path) else [e.jsonable(x) for x in v] if type(v) in (list,tuple) else {k:e.jsonable(x) for k,x in v.items()} if type(v) is dict else old.evidence_value(v))
    e.core_input_point=o.points
    setup=load(STORE,'task037_setup_frozen_store');o.instrument(setup)
    o.allowed_reads=set(setup.COMPONENT_PATHS.values())|{HISTORY}
    base_source=read(SOURCE);base=[base_source[k] for k in ('submission','materials','expectations','prior_history')]
    people=[read(p)['human_values'] for p in HUMANS];source_ids={}
    for p in (SOURCE,*HUMANS):
        raw=p.read_bytes();source_ids[p.relative_to(ROOT).as_posix()]={'byte_size':len(raw),'sha256':sha(raw)}
        with (out/(p.name+'.source.bin')).open('xb') as f:f.write(raw)
    def values(batch,event=0,prior=None,scope=SCOPE):
        def replace(v):
            if type(v) is dict:return {k:replace(x) for k,x in v.items()}
            if type(v) is list:return [replace(x) for x in v]
            return batch if v==base[0]['batch_id'] else v
        v=replace(copy.deepcopy(base));human=people[event]
        for k in ('event_id','decided_at_raw','assessment','reason'):v[0][k]=human[k]
        for k in ('actor_id','declaration_note'):v[0]['actor'][k]=human[k]
        v[3]={'declared_complete':True,'declared_scope':scope,'records':copy.deepcopy(prior or [])}
        v[2]['expected_history_scope']=scope;v[2]['expected_prior_history_fingerprint']=fp(v[3])
        digest=fp({k:x for k,x in v[1].items() if k!='materials_fingerprint'})
        v[1]['materials_fingerprint']=v[0]['request_binding']['materials_fingerprint']=v[2]['expected_materials_fingerprint']=digest
        return v
    def invoke(label,fn,*a,category='history',field=None,stage=None,nverify=None,ncore=None,controlled=False,**kw):
        before=dict(o.api);refs=[*a[:3],kw.get('prior_history')] if category=='setup_store_save' else [kw.get('expectations')]
        points=o.points(refs);path=kw['out_dir'] if category=='setup_store_save' else a[0];before_scene=scene(path,root);after=[];native=[]
        def called(*args,**kwargs):
            try:
                with o.guard(setup=category=='setup_store_save'):
                    result=fn(*args,**kwargs);native.append(result);return result
            finally:after.extend(o.points(refs))
        err,result,cid=e.call_api(h,label,called,*a,**kw)
        after_scene=scene(path,root);delta={k:o.api[k]-before[k] for k in o.api}
        e.API_RECORDS[-1].update(record_category=category,actual_entries=delta,reasons=copy.deepcopy(getattr(err,'reasons',None)),
            input_refs_before=points,input_refs_after=after,input_refs_api_end=o.points(refs),
            path_scene_before=before_scene,path_scene_api_end=after_scene,test_control_injection=controlled)
        for row in e.CORE_RECORDS:
            if row['caller_api']==cid and row['core']=='store_verify':row['path_scene_api_end']=scene(Path(row['args'][0]['$path']),root)
        if field:ok=isinstance(err,h.HumanInitialJudgmentHistoryBlocked) and err.field==field and err.reasons==[err.reason]
        elif stage:ok=isinstance(err,h.HumanInitialJudgmentHistoryError) and err.stage==stage and bool(err.__cause__)
        else:ok=err is None
        ok=ok and (nverify is None or delta['store_verify']==nverify) and (ncore is None or delta['pure_core']==ncore)
        if category=='history' and not controlled:ok=ok and canon(before_scene)==canon(after_scene)
        e.check(label,ok,{'call_id':cid,'actual':type(err).__name__,'field':getattr(err,'field',None),'stage':getattr(err,'stage',None),'delta':delta})
        return err,result,cid,(native[0] if native else None)
    def save(leaf,v):
        err,result,*_=invoke('setup.'+leaf.parent.name+'.'+leaf.name,setup.save_human_initial_judgment_snapshots,*v[:3],prior_history=v[3],out_dir=leaf,category='setup_store_save',ncore=1,nverify=0)
        assert err is None;return result
    def index_of(r):
        rec=r['judgment_result']['record'];return {'event_id':rec['human_initial_judgment']['event_id'],'batch_id':rec['binding']['batch_id'],'record_fingerprint':fp(rec),'binding_fingerprint':fp(rec['binding'])}
    def expect(ns):
        return {'expectations_version':'TASK-037-human-initial-judgment-history-expectations-1.0','expected_namespace_relative':ns.relative_to(ROOT).as_posix(),
            'expected_declared_scope':SCOPE,'expected_entries':[{'relative':p.name,'manifest_file_sha256':sha((p/'manifest.json').read_bytes())} for p in sorted(ns.iterdir(),key=lambda p:p.name.encode('utf-8'))]}
    unspecified=object()
    def inspect(label,ns,ex=unspecified,**opts):return invoke(label,h.inspect_human_initial_judgment_history,ns,expectations=expect(ns) if ex is unspecified else ex,**opts)
    def copy_namespace(ns,name,omit=()):
        dst=root/name;dst.mkdir()
        for p in ns.iterdir():
            leaf=dst/p.name;leaf.mkdir()
            for f in p.iterdir():
                if f.name not in omit:
                    with (leaf/f.name).open('xb') as stream:stream.write(f.read_bytes())
        return dst
    sys.setprofile(o.profile)
    try:
        with o.guard(prove=True):
            for p in (lambda:io.open(root/'GUARD_MUST_NOT_EXIST','wb'),socket.socket,lambda:subprocess.Popen(['TASK037_MUST_NOT_RUN']),datetime.datetime.now):
                try:p()
                except AssertionError:pass
        e.check('guard.proven',o.proof==['write','network','subprocess','clock'])
        empty=root/'empty';empty.mkdir();_,empty_result,_,_=inspect('normal.empty',empty,nverify=0,ncore=0)
        one=root/'one';one.mkdir();r1=save(one/'z_first',values('TECH037-BATCH-A'))
        _,one_result,one_call_id,_=inspect('normal.one',one,nverify=1,ncore=1)
        first_verify=next(r for r in e.CORE_RECORDS if r['caller_api']==one_call_id and r['core']=='store_verify')
        i1=index_of(first_verify['return'])
        put(out/'fixed_prior_reference_source.json',{'source':'earlier actual frozen store verify complete observation; fixed before second setup save',
            'call_id':one_call_id,'nested_id':first_verify['nested_id'],'full_verification':first_verify['return'],'fixed_four_field_index':i1})
        two=copy_namespace(one,'two');r2=save(two/'a_second',values('TECH037-BATCH-B',1,[i1]))
        ex2=expect(two);_,two_result,_,native=inspect('normal.two',two,ex2,nverify=2,ncore=2)
        def expected(ns,store_results):
            prior={'declared_complete':True,'declared_scope':SCOPE,'records':sorted([index_of(x) for x in store_results.values()],key=lambda x:x['event_id'].encode('utf-8'))}
            entries=expect(ns)['expected_entries'];inventory={'namespace_relative':ns.relative_to(ROOT).as_posix(),'declared_scope':SCOPE,'entries':entries}
            components={k:sha(p.read_bytes()) for k,p in setup.COMPONENT_PATHS.items()};components['history_file_sha256']=sha(HISTORY.read_bytes())
            verified=[]
            for name,r in sorted(store_results.items()):
                v=copy.deepcopy(r);v['status']='HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_VERIFIED';verified.append({'relative':name,'verification':v})
            return {'history_version':'TASK-037-human-initial-judgment-history-1.0','status':'HUMAN_INITIAL_JUDGMENT_NAMESPACE_INSPECTED','scope':'DECLARED_NAMESPACE_CURRENT_SNAPSHOTS_ONLY',
                'namespace_relative':ns.relative_to(ROOT).as_posix(),'prior_history':prior,'prior_history_fingerprint':fp(prior),'inventory':inventory,'inventory_fingerprint':fp(inventory),
                'component_bindings':components,'verified_snapshots':verified,'boundaries':{k:False for k in ('workflow_connected','execution_allowed','next_step_allowed','ai_enabled','identity_authenticated','source_authenticity_proven','audit_conclusion_formed','final_judgment_recorded','global_history_completeness_proven')},
                'note':'仅核验本次声明命名域的现存成功快照及已声明历史引用；不证明历史从未删失，不批准执行，不认证身份，不开放AI或终判。'}
        independent={'empty':expected(empty,{}),'one':expected(one,{'z_first':r1}),'two':expected(two,{'a_second':r2,'z_first':r1})}
        e.check('normal.complete_independent',all(canon(got)==canon(independent[k]) for k,got in [('empty',empty_result),('one',one_result),('two',two_result)]))
        e.check('normal.sorted_events',[x['event_id'] for x in two_result['prior_history']['records']]==['1','2'] and [x['relative'] for x in two_result['verified_snapshots']]==['a_second','z_first'])
        fixed=canon(ex2);native['prior_history']['records'][0]['batch_id']='TEST_RETURN_MUTATION';native['verified_snapshots'][0]['verification']['snapshots']['submission']['reason']='TEST_RETURN_MUTATION'
        e.check('normal.no_alias',canon(ex2)==fixed and r1['identity']['batch_id']=='TECH037-BATCH-A' and r2['snapshots']['submission']['reason']==people[1]['reason'])
        put(out/'independent_normal_expectations.json',independent)
        for name,v,field in [('duplicate_event',values('TECH037-BATCH-C',0),'entries[1].record.human_initial_judgment.event_id'),('duplicate_batch',values('TECH037-BATCH-A',1),'entries[1].record.binding.batch_id')]:
            ns=copy_namespace(one,name);save(ns/'zz_second',v);inspect('relations.'+name,ns,field=field,nverify=2,ncore=2)
        for name,scope,edit,field in (
            ('scope','OTHER-DECLARED-SCOPE',lambda x:None,'entries[0].prior_history.declared_scope'),
            ('missing_reference',SCOPE,lambda x:None,'entries[0].prior_history.records[0].event_id'),
            ('wrong_record',SCOPE,lambda x:x.__setitem__('record_fingerprint','0'*64),'entries[0].prior_history.records[0].record_fingerprint'),
            ('wrong_binding',SCOPE,lambda x:x.__setitem__('binding_fingerprint','0'*64),'entries[0].prior_history.records[0].binding_fingerprint'),
            ('wrong_batch',SCOPE,lambda x:x.__setitem__('batch_id','TECH037-WRONG'),'entries[0].prior_history.records[0].batch_id')):
            ns=root/name;ns.mkdir();ref=copy.deepcopy(i1);edit(ref)
            if name not in ('scope','missing_reference'):
                (ns/'z_first').mkdir()
                for f in (one/'z_first').iterdir():
                    with (ns/'z_first'/f.name).open('xb') as s:s.write(f.read_bytes())
            save(ns/'a_second',values('TECH037-BATCH-B',1,[] if name=='scope' else [ref],scope));inspect('relations.'+name,ns,field=field,nverify=1 if name=='scope' else (1 if name=='missing_reference' else 2),ncore=1 if name in ('scope','missing_reference') else 2)
        ex=expect(empty)
        for name,edit,field in [('null',lambda v:None,'expectations'),('missing',lambda v:{k:x for k,x in v.items() if k!='expected_entries'},'expectations.expected_entries'),
            ('extra',lambda v:dict(v,extra=1),'expectations.extra'),('entries_null',lambda v:dict(v,expected_entries=None),'expectations.expected_entries'),
            ('sha_LF',lambda v:dict(v,expected_entries=[{'relative':'a','manifest_file_sha256':'a'*64+'\n'}]),'expectations.expected_entries[0].manifest_file_sha256'),
            ('relative_bad',lambda v:dict(v,expected_namespace_relative='../outside'),'expectations.expected_namespace_relative'),
            ('leaf_bad',lambda v:dict(v,expected_entries=[{'relative':'a/..','manifest_file_sha256':'a'*64}]),'expectations.expected_entries[0].relative'),
            ('unsorted',lambda v:dict(v,expected_entries=[{'relative':n,'manifest_file_sha256':'a'*64} for n in ('b','a')]),'expectations.expected_entries[1].relative')]:
            inspect('schema.'+name,empty,edit(copy.deepcopy(ex)),field=field,nverify=0,ncore=0)
        for name,path,field in [('missing',root/'absent','namespace_dir.record_dir'),('root',RECORD_ROOT,'namespace_dir.record_dir'),('outside',out,'namespace_dir.record_dir')]:
            inspect('path.'+name,path,ex,field=field,nverify=0,ncore=0)
        wrong_ex=copy.deepcopy(ex);wrong_ex['expected_namespace_relative']=one.relative_to(ROOT).as_posix();inspect('path.expected_wrong',empty,wrong_ex,field='expectations.expected_namespace_relative',nverify=0,ncore=0)
        few=expect(two);few['expected_entries']=few['expected_entries'][:1];inspect('inventory.missing_declared',two,few,field='expectations.expected_entries',nverify=0,ncore=0)
        more=expect(empty);more['expected_entries']=[{'relative':'missing','manifest_file_sha256':'a'*64}];inspect('inventory.missing_actual',empty,more,field='expectations.expected_entries',nverify=0,ncore=0)
        rootfile=root/'rootfile';rootfile.mkdir();put(rootfile/'unknown.json',{});inspect('inventory.root_file',rootfile,ex|{'expected_namespace_relative':rootfile.relative_to(ROOT).as_posix()},field='namespace_dir.unknown.json',nverify=0,ncore=0)
        for name,omit,edit,field,n in [('failure',(),lambda leaf:put(leaf/'failure.json',[]),'entries[0].failure.json',0),
            ('missing_payload',('materials.json',),lambda leaf:None,'entries[0].files',0),
            ('truncated',(),lambda leaf:(leaf/'expectations.json').write_bytes((leaf/'expectations.json').read_bytes()[:10]),'entries[0].expectations.json',0),
            ('subtree',(),lambda leaf:(leaf/'nested').mkdir(),'entries[0].files',0),
            ('component',(),lambda leaf:None,'entries[0].manifest.component_bindings',1)]:
            ns=copy_namespace(one,name,omit);leaf=ns/'z_first';edit(leaf)
            if name=='component':
                obj=read(leaf/'manifest.json');obj['component_bindings']['core_file_sha256']='0'*64;(leaf/'manifest.json').write_bytes(canon(obj)+b'\n')
            inspect('leaf.'+name,ns,field=field,nverify=n,ncore=0)
        failure_call=next(r['call_id'] for r in e.API_RECORDS if r['operation']=='leaf.failure')
        e.check('leaf.failure_before_manifest',not any(x['parent_call_id']==failure_call and x['path'].endswith('manifest.json') for x in o.io))
        # Synthetic raw-path reparse control consumes a real alias lstat result.
        alias=root/'raw_alias';alias.mkdir();raw_path=alias/'..'/one.name;real_lstat=Path.lstat;hits=[]
        def lstat(p,*a,**k):
            actual=real_lstat(p,*a,**k)
            if p==alias:hits.append(str(p));return SimpleNamespace(st_mode=actual.st_mode,st_file_attributes=getattr(actual,'st_file_attributes',0)|0x400)
            return actual
        Path.lstat=lstat
        try:inspect('path.raw_metadata',raw_path,expect(one),field='namespace_dir.record_dir',nverify=0,ncore=0)
        finally:Path.lstat=real_lstat
        alias_hit_count=len(hits);e.check('path.raw_consumed',alias_hit_count==1)
        # Keep the real frozen verify; mutate only its returned object afterwards.
        real_load=h._load_store
        def contradictory():
            m,b=real_load();real=m.verify_human_initial_judgment_snapshots
            def wrong(*a,**k):r=real(*a,**k);r['judgment_result']['record_fingerprint']='0'*64;return r
            m.verify_human_initial_judgment_snapshots=wrong;return m,b
        h._load_store=contradictory
        try:inspect('leaf.full_return_contradiction',one,field='entries[0].verification.judgment_result',nverify=1,ncore=1)
        finally:h._load_store=real_load
        real_read=Path.read_bytes;read_hits=[]
        def read_error(p):
            raw=real_read(p)
            if p==one/'z_first'/'manifest.json' and sys._getframe(1).f_code.co_name=='_read_bytes':read_hits.append(1);raise OSError('TASK037_CONTROLLED_READ_ERROR')
            return raw
        ex_one=expect(one);Path.read_bytes=read_error
        try:err,*_=inspect('error.actual_read_boundary',one,ex_one,stage='read',nverify=0,ncore=0)
        finally:Path.read_bytes=real_read
        e.check('error.original_chain',read_hits==[1] and 'OSError' in ' '.join(e.chain_of(err)) and err.reason.endswith('TASK037_CONTROLLED_READ_ERROR'))
        # A copied frozen source is used for the late component control; no
        # frozen project source is ever changed or authorized for writing.
        copied=out/'core.source.control.bin';component_original=setup.COMPONENT_PATHS['core_file_sha256'].read_bytes();copied.write_bytes(component_original);o.allowed_reads.add(copied)
        captured_open=io.open;component_hits=[];real_capture=h._capture_leaf
        def redirected_load():
            m,b=real_load();m.COMPONENT_PATHS['core_file_sha256']=copied;return m,b
        def component_late(*a,**k):
            value=real_capture(*a,**k)
            with captured_open(copied,'ab') as s:s.write(b'\n')
            component_hits.append(1);return value
        h._load_store=redirected_load;h._capture_leaf=component_late
        try:inspect('late.component_before_store',one,field='component_bindings.core_file_sha256',nverify=0,ncore=0)
        finally:h._load_store=real_load;h._capture_leaf=real_capture
        e.check('late.component_hit',component_hits==[1])
        late=copy_namespace(one,'late_leaf');late_ex=expect(late);target=late/'z_first'/'judgment_result.json';original=target.read_bytes();real_return=h._build_return;hits=[]
        def late_return(*a,**k):
            r=real_return(*a,**k)
            with captured_open(target,'ab') as s:s.write(b'\n')
            hits.append(1);return r
        h._build_return=late_return
        try:inspect('late.leaf_after_consumption',late,late_ex,field='entries[0].judgment_result.json',nverify=1,ncore=1,controlled=True)
        finally:h._build_return=real_return
        inspect('late.retained_bad',late,late_ex,field='entries[0].judgment_result.json',nverify=0,ncore=0)
        with (out/'late_judgment.bad.bin').open('xb') as s:s.write(target.read_bytes())
        target.write_bytes(original);inspect('late.exact_own_restore',late,late_ex,nverify=1,ncore=1)
        e.check('late.once_no_failure',hits==[1] and not (late/'z_first'/'failure.json').exists())
        late_ns=copy_namespace(one,'late_namespace');late_ex=expect(late_ns);hits=[];control_mkdir=os.mkdir
        def added_member(*a,**k):r=real_return(*a,**k);control_mkdir(late_ns/'unknown_new_leaf');hits.append(1);return r
        h._build_return=added_member
        try:inspect('late.new_member',late_ns,late_ex,field='expectations.expected_entries',nverify=1,ncore=1,controlled=True)
        finally:h._build_return=real_return
        inspect('late.member_retained',late_ns,late_ex,field='expectations.expected_entries',nverify=0,ncore=0)
        e.check('late.member_once',hits==[1])
        e.check('observations.frames_closed',o.api['history']==sum(a['record_category']=='history' for a in e.API_RECORDS)
            and o.api['setup_store_save']==sum(a['record_category']=='setup_store_save' for a in e.API_RECORDS)
            and o.api['store_verify']==sum(a['core']=='store_verify' for a in e.CORE_RECORDS)
            and o.api['pure_core']==sum(a['core']=='pure_core' for a in e.CORE_RECORDS),o.api)
        e.check('observations.inputs_three_points',all(canon(r['input_refs_before'])==canon(r['input_refs_after'])==canon(r['input_refs_api_end']) for r in e.CORE_RECORDS)
            and all(canon(r['input_refs_before'])==canon(r['input_refs_after'])==canon(r['input_refs_api_end']) for r in e.API_RECORDS))
        e.check('guards.production_clean',not o.guards and not o._other,{'hits':o.guards,'other':o._other})
        history_ids={r['call_id'] for r in e.API_RECORDS if r['record_category']=='history'}
        e.check('guards.history_writes_zero',not any(x['writing'] and x['parent_call_id'] in history_ids for x in o.io))
        put(out/'io_observations.json',{'events':o.io,'guard_proof':o.proof,'production_hits':o.guards,'other_business':o._other})
        put(out/'controls.json',{'raw_alias_hits':alias_hit_count,'physical_junction':{'count':None,'reason':'prior OS permission refusal; synthetic metadata control only'},
            'component_copy_hits':len(component_hits),'component_copy':str(copied),'component_before_sha256':sha(component_original),'component_after_sha256':sha(copied.read_bytes()),
            'no_frozen_source_modified':setup.COMPONENT_PATHS['core_file_sha256'].read_bytes()==component_original,
            'late_original_sha256':sha(original),'late_bad_sha256':sha((out/'late_judgment.bad.bin').read_bytes())})
    except Exception:
        put(out/'process_exception.json',{'traceback':traceback.format_exc(),'API_records':e.API_RECORDS,'nested_records':e.CORE_RECORDS,'actual_code_entries':o.api})
        raise
    finally:sys.setprofile(None)
    for p,v in source_ids.items():assert sha((ROOT/p).read_bytes())==v['sha256']
    return o,{'scope':'DECLARED_NAMESPACE_CURRENT_SNAPSHOTS_ONLY','actual_code_entries':o.api,'source_identities':source_ids,
        'not_executed':{'physical_junction':None,'workflow_full_history_AI':None,'extra_human_time_positives':None},
        'not_executed_reason':'OS permission refusal retained; workflow/global history/AI outside scope; extra human values unprovided'}

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--out-dir',required=True);p.add_argument('--replay');p.add_argument('--mutate',choices=('none','candidate-return','ledger-late','checks-late'),default='none')
    a=p.parse_args(argv);out=Path(a.out_dir).resolve()
    if out==TEST_ROOT or not out.is_relative_to(TEST_ROOT) or out.exists() or not out.name.startswith('task037_'):raise SystemExit('fresh task037_ strict descendant required')
    old=load(ROOT/'tests/test_build_demo_human_initial_judgment.py','task037_readonly_observation_helpers');e=old.evidence_module();e.ROUND['id']=out.name
    original_build=e.build_candidate
    def build(*args,**kw):
        result=original_build(*args,**kw);result['summary']['task']='TASK-037';result['summary']['scope']='DECLARED_NAMESPACE_CURRENT_SNAPSHOTS_ONLY'
        o=args[1];result['summary']['observed']={'actual_code_entries':o.api if o else None,'replay_new_calls':None if o else 'external original-code profiler'}
        result['summary']['record_categories']={role:sum(r.get('record_category')==role for r in result['api_records']) for role in ('history','setup_store_save')}
        result['summary']['record_categories'].update({role:sum(r.get('core')==role for r in result['core_records']) for role in ('store_verify','pure_core')})
        return result
    e.build_candidate=build;out.mkdir(parents=True,exist_ok=False)
    if a.replay:
        source=Path(a.replay).resolve()
        if not source.is_relative_to(TEST_ROOT) or source==out or not source.name.startswith('task037_'):raise SystemExit('invalid replay source')
        checkpoint=read(source/'expected_observations.json');o=None;extra={'replay_only':True,'source':str(source)}
    else:
        if a.mutate!='none':raise SystemExit('mutate requires replay')
        o,extra=run(e,old,out);checkpoint=e.freeze_expectations()
    real_read=Path.read_bytes;control={'hits':0}
    if a.mutate.endswith('-late'):
        def read_mutate(path):
            raw=real_read(path);frame=sys._getframe(1)
            if frame.f_code is e.finish.__code__ and 'terminal_buffers' in frame.f_locals and path==out/'expected_observations.json' and not control['hits']:
                target=out/('file_ledger.json' if a.mutate=='ledger-late' else 'checks.json');before=real_read(target)
                with target.open('ab') as s:s.write(b'\n')
                control.update(hits=1,target=target.name,before_size=len(before),after_size=len(before)+1,before_sha256=sha(before),after_sha256=sha(before+b'\n'))
            return raw
        Path.read_bytes=read_mutate
    try:code=e.finish(out,checkpoint,'candidate-return' if a.mutate=='candidate-return' else 'none',o,extra)
    finally:Path.read_bytes=real_read
    if a.mutate.endswith('-late'):put(out/'control_observation.json',control)
    return code
if __name__=='__main__':raise SystemExit(main())
