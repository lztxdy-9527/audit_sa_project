"""TASK-038 one new prerequisite chain and finite read-only request controls."""
from __future__ import annotations
import argparse,ast,builtins,copy,datetime,hashlib,importlib.util,io,json,os,random,secrets,socket,sqlite3,subprocess,sys,traceback,types,uuid
from contextlib import contextmanager
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TEST_ROOT=ROOT/'data/runtime_initial_judgment_request_tests';BATCH=ROOT/'data/batches/task027r1_run_04/batch_normal'
RUNTIME=ROOT/'scripts/runtime_gate1.py'
BUSINESS=('build_runtime_registry','read_runtime_registry','prepare_runtime_gate1_request','save_runtime_gate1_decision','verify_gate1_effective_approval',
 'run_gate1_approved_load','inspect_gate1_approved_load','prepare_runtime_gate2_request','save_runtime_gate2_decision','verify_runtime_gate2_decision',
 'run_gate2_approved_screen','inspect_gate2_approved_screen','run_gate2_rule_crosscheck','inspect_gate2_rule_crosscheck','run_gate2_fact_packet','inspect_gate2_fact_packet','prepare_runtime_initial_judgment_request')
SCOPE='TASK037-DECLARED-TECHNICAL-NAMESPACE'
def canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def sha(b):return hashlib.sha256(b).hexdigest()
def fp(v):return sha(canon(v))
def read(p):return json.loads(p.read_bytes())
def put(p,v):
    with p.open('xb') as f:f.write(canon(v)+b'\n')
def load(p,name):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def identity(p):
    raw=p.read_bytes();return {'byte_size':len(raw),'sha256':sha(raw)}
def literal(path,name):
    for node in ast.parse(path.read_bytes()).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):return ast.literal_eval(node.value)
    raise AssertionError('missing frozen constant '+name)
@contextmanager
def patched(obj,name,value):
    previous=getattr(obj,name);setattr(obj,name,value)
    try:yield previous
    finally:setattr(obj,name,previous)
def own_scene(roots):
    """Bounded observation of this round only; never traverse a project root."""
    result={}
    for root in roots:
        if not root.exists():continue
        todo=[(root,0)];seen=0
        while todo:
            path,depth=todo.pop();assert depth<=6
            for p in path.iterdir():
                seen+=1;assert seen<1500
                assert not p.is_symlink()
                if p.is_dir():todo.append((p,depth+1))
                else:result[p.relative_to(ROOT).as_posix()]=identity(p)
    return result
def changed_scene(before,after):return sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
def prove_guard(e,o,leaf):
    phase=o.phase;o.phase='request'
    with o.guard(prove=True):
        for fn in (lambda:io.open(leaf/'must_not_exist','xb'),lambda:socket.socket(),lambda:subprocess.Popen(['not-executed']),lambda:datetime.datetime.now()):
            try:fn()
            except AssertionError:pass
    o.phase=phase;e.check('continuation.guard_proven',o.proof==['write','network','subprocess','clock'] and not (leaf/'must_not_exist').exists(),o.proof)
def validate_prefix(e,rt,out,source,registry,o):
    """New read-only validations of retained observations, not recovery of lost checks."""
    fields={'history.bad_expected_namespace_relative':'history_expectations.expected_namespace_relative','history.bad_expected_declared_scope':'history_expectations.expected_declared_scope',
        'history.bad_expected_entries':'history.expectations.expected_entries','profile.bad_none':'initial_judgment_history','profile.bad_missing':'initial_judgment_history',
        'profile.bad_unsafe':'initial_judgment_history.namespace_relative','profile.reparse_metadata_control':'initial_judgment_history.namespace_relative',
        'profile.changed_domain_gate1_rejected':'context.registry_file_sha256','late.code_copy_view':'registry.run_binding.code.file_sha256',
        'mapping.gate1_not_effective':'gate1.effective','mapping.gate2_not_approve':'gate2.verification','mapping.facts_wrong_complete':'facts.verification',
        'candidate.false_to_int':'initial.request','candidate.int_to_float':'initial.request','candidate.fact_context':'initial.request','late.fact':'facts.fact_packet.json',
        'late.fact_retained':'facts.artifacts','history.blocked_mapping':'history.controlled_field','late.history_append':'history.expectations.expected_entries','late.history_retained':'history.expectations.expected_entries'}
    for row in e.API_RECORDS:
        name=row['operation']
        if name in fields:ok=row['outcome']=='exception' and row['exception_type']=='RuntimeGate1Blocked' and row['field']==fields[name] and bool(row['traceback'])
        elif name=='history.error_mapping':ok=row['exception_type']=='RuntimeGate1Error' and row['stage']=='controlled_history_io' and row['reasons']==['TASK038_TEST_INJECTION'] and any('OSError' in s for s in row['cause_chain'])
        else:ok=name.startswith('setup.') or name in ('request.empty','late.fact_restored','profile.changed_domain_public_read');ok=ok and row['outcome']=='returned'
        e.check('prior_segment.validate.'+name,ok,{'source_call_id':row['call_id'],'new_business_call':False})
    normal=next(r for r in e.API_RECORDS if r['operation']=='request.empty')
    e.check('prior_segment.complete_empty_request',canon(normal['return'])==canon(read(source/'independent_empty_request.json')))
    e.check('prior_segment.empty_readonly',normal['path_scene_before']==normal['path_scene_api_end'])
    labels={}
    for r in e.CORE_RECORDS:labels[r['core']]=labels.get(r['core'],0)+1
    e.check('prior_segment.observation_closure',labels=={k:v for k,v in o.prefix_api.items() if v} and len({r['nested_id'] for r in e.CORE_RECORDS})==len(e.CORE_RECORDS))
    profile=read(source/'profile.json');m=profile['gate1_request']['request']['materials'];body={k:v for k,v in m.items() if k!='materials_fingerprint'}
    original=ROOT/'data/runtime_initial_judgment_request_tests/task038_prepare_01/runtime.before.bin'
    names=sorted((*literal(original,'CODE_FILES'),'scripts/build_demo_human_initial_judgment.py','scripts/store_demo_human_initial_judgment.py','scripts/inspect_demo_human_initial_judgment_history.py','scripts/runtime_gate1.py'))
    code={'manifest_version':'TASK-038-code-manifest-1.0','entries':[{'relative':p,'file_sha256':identity(ROOT/p)['sha256']} for p in names]}
    e.check('prior_segment.profile_identity',len(registry)==14 and len(m['files'])==38 and canon(code)==canon(registry['code_manifest']) and fp(body)==m['materials_fingerprint'])
    for item in m['files']:
        prefix,relative=item['relative'].split('/',1)
        path=(BATCH/relative if prefix=='batch' else ROOT/relative if prefix=='project' else ROOT/'data/runtime'/source.name/'normal'/relative)
        e.check('prior_segment.Gate1_file.'+item['relative'],identity(path)=={'byte_size':item['byte_size'],'sha256':item['file_sha256']})
    late=(source/'fact_packet.late.bin').read_bytes();raw=(source/'fact_packet.original.bin').read_bytes()
    e.check('prior_segment.fact_late_original_and_bad',late==raw+b'\n' and (ROOT/'data/runtime'/source.name/'normal.facts/fact_packet.json').read_bytes()==raw)

def independent_request(leaf,namespace,params,registry,request_id,history_expected,source_bytes):
    """Test-owned complete expectation. No runtime assembly/FP helpers are used."""
    def obj(p):return json.loads(source_bytes[str(p)])
    def file(p):
        b=source_bytes[str(p)];return {'relative':p.relative_to(ROOT).as_posix(),'file_sha256':sha(b),'byte_size':len(b)}
    facts=leaf.with_name(leaf.name+'.facts');g1=ROOT/params['event_relative'];g2=ROOT/params['gate2_event_relative']
    d1=obj(g1/'snapshots/decision_result.json');d2=obj(g2/'snapshots/decision_result.json');packet=obj(facts/'fact_packet.json')
    def link(d,p,gate):
        r=d['record'];b=r['binding'];v={'gate':gate,'batch_id':r['batch_id'],'event_id':r['event_id'],
            'record_fingerprint':fp(r),'record_file_sha256':file(p)['file_sha256'],'materials_fingerprint':b['materials_fingerprint'],
            'contract_binding':copy.deepcopy(b['contract_binding']),'run_binding':copy.deepcopy(b['run_binding']),
            'decision':r['decision'],'actor_kind':r['actor']['actor_kind']}
        if gate=='GATE2':v['prior_gate1_fingerprint']=r['prior_gate1']['record_fingerprint']
        return v
    l1=link(d1,g1/'snapshots/decision_result.json','GATE1');l2=link(d2,g2/'snapshots/decision_result.json','GATE2')
    g1v={'verification_version':'TASK-025-gate1-effective-approval-1.0','batch_id':registry['batch_id'],'event_relative':params['event_relative'],
        'record_fingerprint':l1['record_fingerprint'],'record_file_sha256':l1['record_file_sha256'],'run_binding_sha256':fp(registry['run_binding']),
        'materials_fingerprint':l1['materials_fingerprint'],'decision':'APPROVE','actor_kind':'HUMAN_DECLARED','effective':True,'reasons':[]}
    g2v=dict(copy.deepcopy(d2),event_relative=params['gate2_event_relative'])
    factv={'stage_version':'TASK-033-fact-packet-1.0','status':'RT_FACT_PACKET_RECORDED','batch_id':registry['batch_id'],
        'run_binding_sha256':fp(registry['run_binding']),'artifacts':obj(facts/'artifacts.json'),
        'boundaries':{k:False for k in ('human_initial_judgment_saved','ai_enabled','audit_conclusion_formed','identity_authenticated','source_authenticity_proven','next_step_allowed')}}
    # Full history/store projections are constructed from the pre-call six-file buffers.
    storepath=ROOT/'scripts/store_demo_human_initial_judgment.py';hpath=ROOT/'scripts/inspect_demo_human_initial_judgment_history.py'
    components={k:file(p)['file_sha256'] for k,p in {
        'core_file_sha256':ROOT/'scripts/build_demo_human_initial_judgment.py','store_file_sha256':storepath,
        'protocol_file_sha256':ROOT/'docs/proposals/HUMAN_INITIAL_JUDGMENT_PROTOCOL_V1_DRAFT.md',
        'cases_file_sha256':ROOT/'docs/proposals/HUMAN_INITIAL_JUDGMENT_CASES_V1_DRAFT.md',
        'contract_file_sha256':ROOT/'docs/AUDIT_CONTRACT.md','contract_effective_record_file_sha256':ROOT/'docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md'}.items()}
    verified=[];index=[]
    for entry in history_expected['expected_entries']:
        root=namespace/entry['relative'];names=sorted(p.name for p in root.iterdir());objects={n:obj(root/n) for n in names};manifest=objects['manifest.json'];record=objects['judgment_result.json']['record']
        sv={'status':'HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_VERIFIED','scope':'STORED_SNAPSHOTS_ONLY','identity':manifest['identity'],
            'record_fingerprint':fp(record),'manifest_file_sha256':file(root/'manifest.json')['file_sha256'],'technical_registration':manifest['technical_registration'],
            'component_bindings':components,'files':[dict(file(root/n),relative=n,object_fingerprint=fp(objects[n])) for n in names],
            'boundaries':manifest['boundaries'],'snapshots':{k:objects[k+'.json'] for k in ('submission','materials','expectations','prior_history')},'judgment_result':objects['judgment_result.json']}
        verified.append({'relative':entry['relative'],'verification':sv});index.append({'event_id':record['human_initial_judgment']['event_id'],
            'batch_id':record['binding']['batch_id'],'record_fingerprint':fp(record),'binding_fingerprint':fp(record['binding'])})
    index.sort(key=lambda v:v['event_id'].encode('utf-8'));prior={'declared_complete':True,'declared_scope':SCOPE,'records':index}
    inventory={'namespace_relative':namespace.relative_to(ROOT).as_posix(),'declared_scope':SCOPE,'entries':copy.deepcopy(history_expected['expected_entries'])}
    hv={'history_version':'TASK-037-human-initial-judgment-history-1.0','status':'HUMAN_INITIAL_JUDGMENT_NAMESPACE_INSPECTED',
        'scope':'DECLARED_NAMESPACE_CURRENT_SNAPSHOTS_ONLY','namespace_relative':inventory['namespace_relative'],'prior_history':prior,
        'prior_history_fingerprint':fp(prior),'inventory':inventory,'inventory_fingerprint':fp(inventory),
        'component_bindings':dict(components,history_file_sha256=file(hpath)['file_sha256']),'verified_snapshots':verified,
        'boundaries':{k:False for k in literal(hpath,'BOUNDARIES')},'note':literal(hpath,'NOTE')}
    paths={'facts.started':facts/'started.json','facts.packet':facts/'fact_packet.json','facts.markdown':facts/'fact_packet.md','facts.artifacts':facts/'artifacts.json',
        'runtime.registry':leaf/'runtime_registry.json','contract':ROOT/'docs/AUDIT_CONTRACT.md','gate1.record':g1/'snapshots/decision_result.json','gate2.record':g2/'snapshots/decision_result.json'}
    files=sorted([dict(file(p),role=role) for role,p in paths.items()],key=lambda v:v['relative'].encode('utf-8'))
    fs={'inspect_binding':{k:factv[k] for k in ('stage_version','status','batch_id','run_binding_sha256')},'packet':packet,
        'packet_canonical_sha256':fp(packet),'finding_ids':[v['finding_id'] for v in packet['findings']],
        'source_fingerprints':{k:packet['bindings'][k] for k in ('workbook_sha256','normalized_payload_sha256','screening_report_sha256','crosscheck_report_sha256')}}
    materials={'materials_version':'TASK-034-human-initial-judgment-materials-1.0','batch_id':registry['batch_id'],
        'runtime_version':'TASK-038-runtime-gate1-1.0','entity':packet['entity'],'contract_binding':registry['contract'],'run_binding':registry['run_binding'],
        'fact_snapshot':fs,'gate_links':{'gate1':l1,'gate2':l2},'files':files}
    mfp=fp(materials);materials['materials_fingerprint']=mfp
    expected={'expectations_version':'TASK-034-human-initial-judgment-expectations-1.0','expected_batch_id':registry['batch_id'],'expected_request_id':request_id,
        'expected_materials_fingerprint':mfp,'expected_contract':registry['contract'],'expected_runtime_version':'TASK-038-runtime-gate1-1.0',
        'expected_run_binding':registry['run_binding'],'expected_fact_binding':{k:v for k,v in fs.items() if k!='packet'},
        'expected_gate_links':materials['gate_links'],'expected_files':files,'expected_history_scope':SCOPE,'expected_prior_history_fingerprint':fp(prior)}
    evidence={'gate1_verification':g1v,'gate2_verification':g2v,'fact_verification':factv,'history_verification':hv,
        'registry_binding':{'registry_version':registry['registry_version'],'registry_file_sha256':file(leaf/'runtime_registry.json')['file_sha256'],
        'registry_byte_size':file(leaf/'runtime_registry.json')['byte_size'],'run_binding_sha256':fp(registry['run_binding']),'initial_judgment_history':registry['initial_judgment_history']},
        'contract_effective_record':file(ROOT/'docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md'),'files':files}
    result={'request_version':'TASK-038-human-initial-judgment-request-1.0','status':'RUNTIME_HUMAN_INITIAL_JUDGMENT_REQUEST_PREPARED',
        'materials':materials,'expectations':expected,'evidence':evidence,'boundaries':{k:False for k in literal(RUNTIME,'INITIAL_BOUNDARIES')}}
    return copy.deepcopy({'request':result,'request_sha256':fp(result)})

def _request_controls(e,old,out,rt,o,call,leaf,namespace,binding,params,registry,gate_fields):
    o.phase='diagnostic';records=[];source_bytes={};roots=[p for p in o.allowed_roots if p!=BATCH]
    def capture():
        files=own_scene([BATCH,*roots]);return {str(ROOT/p):(ROOT/p).read_bytes() for p in files}|{str(p):p.read_bytes() for p in o.allowed_reads}
    empty={'expectations_version':'TASK-037-human-initial-judgment-history-expectations-1.0','expected_namespace_relative':binding['namespace_relative'],
        'expected_declared_scope':SCOPE,'expected_entries':[]}
    def request(label,h=empty,**more):return call(label,rt.prepare_runtime_initial_judgment_request,BATCH,leaf,'TECH038-REQUEST\n001',phase='request',history_expectations=h,**params,**more)
    # Exercise the exact read/write/network/subprocess/clock gates before production.
    o.phase='request'
    with o.guard(prove=True):
        for name,fn in [('write',lambda:io.open(leaf/'must_not_exist','xb')),('network',lambda:socket.socket()),
                        ('subprocess',lambda:subprocess.Popen(['not-executed'])),('clock',lambda:datetime.datetime.now())]:
            try:fn()
            except AssertionError:pass
    o.phase='diagnostic';e.check('guard.proven',o.proof==['write','network','subprocess','clock'] and not (leaf/'must_not_exist').exists(),o.proof)
    source_bytes=capture();expected=independent_request(leaf,namespace,params,registry,'TECH038-REQUEST\n001',empty,source_bytes)
    before=own_scene([BATCH,*roots]);err,normal,cid=request('request.empty')
    if err:raise err
    after=own_scene([BATCH,*roots]);e.check('normal.complete_independent',canon(normal)==canon(expected),{'expected_sha256':fp(expected),'actual_sha256':fp(normal),'fixed_before_call':True})
    e.check('normal.readonly',not changed_scene(before,after),changed_scene(before,after));put(out/'independent_empty_request.json',expected)
    rootrow=next(r for r in e.CORE_RECORDS if r['caller_api']==cid and r['core']=='runtime.prepare_runtime_initial_judgment_request')
    direct=[r['core'] for r in e.CORE_RECORDS if r['parent_nested_id']==rootrow['nested_id']]
    counts={key:sum(r['core']==key and r['caller_api']==cid for r in e.CORE_RECORDS) for key in o.api}
    predicted={'runtime.verify_gate1_effective_approval':6,'runtime.verify_runtime_gate2_decision':5,'runtime.inspect_gate1_approved_load':5,
        'runtime.inspect_gate2_approved_screen':2,'runtime.inspect_gate2_rule_crosscheck':1,'runtime.inspect_gate2_fact_packet':1,
        'facts.render':1,'gate.store.verify':11,'gate.core':11,'source.prepare':6,'history':1}
    e.check('normal.call_graph',direct==['runtime.verify_gate1_effective_approval','runtime.verify_runtime_gate2_decision','runtime.inspect_gate2_fact_packet','history'] and all(counts.get(k)==v for k,v in predicted.items()),{'direct':direct,'counts':counts,'predicted':predicted})
    e.check('normal.algorithm_setup_once',all(o.api.get('algorithm.'+n)==1 for n in ('normalize','load','screen','crosscheck','facts_build')),o.api)
    packet=normal['request']['materials']['fact_snapshot']['packet']
    e.check('normal.fact_expected',len(packet['findings'])==1 and packet['findings'][0]['rule_id']=='R02' and '400000' in canon(packet).decode())
    # Return snapshots do not alias the caller's actual history input or other sections.
    def mutable_ids(v):
        if type(v) not in (list,dict,tuple):return set()
        return {id(v)}|set().union(*(mutable_ids(x) for x in (v.values() if type(v) is dict else v)))
    actual=o.return_refs[rootrow['nested_id']];input_ids=set().union(*(mutable_ids(v) for r in e.CORE_RECORDS if r['caller_api']==cid for v in e.CORE_INPUT_REFS[r['nested_id']]))
    no_alias=not (mutable_ids(actual)&input_ids);actual['request']['materials']['entity']['company']='TEST-MUTATION'
    e.check('normal.no_alias',no_alias and empty['expected_entries']==[] and canon(normal)==canon(expected),{'actual_return_reference':id(actual),'inputs_disjoint':no_alias})
    for key,value,field in [('expected_namespace_relative',binding['namespace_relative']+'-other','history_expectations.expected_namespace_relative'),
        ('expected_declared_scope',SCOPE+'-other','history_expectations.expected_declared_scope'),('expected_entries',[{'relative':'absent','manifest_file_sha256':'0'*64}],'history.expectations.expected_entries')]:
        h=copy.deepcopy(empty);h[key]=value;request('history.bad_'+key,h,field=field)
    # Registered profile failure/unsafe/old identity controls execute actual parsers, never old run/main.
    for label,value,field in [('none',None,'initial_judgment_history'),('missing',{},'initial_judgment_history'),
        ('unsafe',dict(binding,namespace_relative=binding['namespace_relative']+'/../bound'),'initial_judgment_history.namespace_relative')]:
        target=leaf.parent/('invalid_'+label)
        call('profile.bad_'+label,rt.build_runtime_registry,BATCH,target,scope_dir=ROOT/'data/human_gate_decision_records/gate1'/out.name/('invalid_'+label),initial_judgment_history=value,field=field,phase='diagnostic')
        e.check('profile.no_target_'+label,not target.exists())
    lstat=Path.lstat;metadata={'hits':0}
    def reparse_meta(path,*a,**k):
        info=lstat(path,*a,**k)
        if path==namespace:
            metadata['hits']+=1
            return types.SimpleNamespace(st_mode=info.st_mode,st_file_attributes=getattr(info,'st_file_attributes',0)|0x400)
        return info
    target=leaf.parent/'invalid_reparse'
    with patched(Path,'lstat',reparse_meta):
        call('profile.reparse_metadata_control',rt.build_runtime_registry,BATCH,target,scope_dir=ROOT/'data/human_gate_decision_records/gate1'/out.name/'invalid_reparse',initial_judgment_history=binding,field='initial_judgment_history.namespace_relative',phase='diagnostic')
    e.check('profile.reparse_no_target',metadata['hits']>0 and not target.exists(),{'synthetic_metadata_not_physical_junction':True,**metadata})
    originalregistry=leaf/'runtime_registry.json';originalreadback=leaf/'runtime_registry_readback.json'
    # A valid self-contained registry with a different domain: read the copy before Gate1 seam.
    alternate=namespace.parent/'alternate';clone=leaf.parent/'alternate_registry'
    changed=copy.deepcopy(registry);changed['initial_judgment_history']['namespace_relative']=alternate.relative_to(ROOT).as_posix()
    assert read(clone/'runtime_registry.json')==changed
    candidate=rt._load_stored_registry(clone,allow_existing_scope=True)
    e.check('profile.changed_domain_registry_valid',canon(candidate[0])==canon(changed))
    originalload=rt._load_stored_registry
    def swap_registry(path,*a,**k):
        value=originalload(path,*a,**k)
        return copy.deepcopy(candidate) if Path(path)==leaf else value
    with patched(rt,'_load_stored_registry',swap_registry):
        call('profile.changed_domain_gate1_rejected',rt.verify_gate1_effective_approval,BATCH,leaf,scope_dir=params['scope_dir'],event_relative=params['event_relative'],field='context.registry_file_sha256',phase='request')
    oldreg=copy.deepcopy(registry);oldreg.pop('initial_judgment_history');oldreg['registry_version']='TASK-026-runtime-registry-1.0'
    try:rt._validate_registry(oldreg)
    except rt.RuntimeGate1Blocked as exc:e.check('profile.old_version',exc.field=='registry.registry_version',{'field':exc.field})
    else:e.check('profile.old_version',False)
    # Late code view uses this round's physical copy. Frozen source is never edited.
    codecopy=out/'runtime.late_source.bin';code_original=RUNTIME.read_bytes()
    with codecopy.open('xb') as f:f.write(code_original+b'\n')
    o.allowed_reads.add(codecopy);file_capture=rt._capture_file;capture_initial=rt._capture_initial_sources_038;codeview={'armed':False,'hits':0}
    def finish_initial(*a,**k):
        ctx=capture_initial(*a,**k);codeview['armed']=True;return ctx
    def code_reader(path,stage):
        value=file_capture(path,stage)
        if Path(path)==RUNTIME and codeview['armed']:
            codeview['hits']+=1;copied=file_capture(codecopy,stage+'.test_copy');return dict(copied,path=str(RUNTIME))
        return value
    with patched(rt,'_capture_initial_sources_038',finish_initial),patched(rt,'_capture_file',code_reader):
        err,_,cid=request('late.code_copy_view',field='registry.run_binding.code.file_sha256')
    e.check('late.code_before_core',codeview['hits']==1 and e.API_RECORDS[-1]['actual_entries'].get('gate.core',0)==0 and RUNTIME.read_bytes()==code_original,codeview)
    # Isolated real-return mappings: preserve actual observed complete returns separately.
    for label,name,mutate,field in [('gate1_not_effective','verify_gate1_effective_approval',lambda v:v.update(effective=False),'gate1.effective'),
        ('gate2_not_approve','verify_runtime_gate2_decision',lambda v:v['record'].update(decision='HOLD'),'gate2.verification'),
        ('facts_wrong_complete','inspect_gate2_fact_packet',lambda v:v['artifacts'].update(packet_file_sha256='0'*64),'facts.verification')]:
        fn=getattr(rt,name);hit={'count':0}
        def mapped(*a,_fn=fn,_mutate=mutate,**k):
            v=_fn(*a,**k);hit['count']+=1;v=copy.deepcopy(v);_mutate(v);return v
        with patched(rt,name,mapped):request('mapping.'+label,field=field)
        e.check('mapping.hit_'+label,hit['count']==1,hit)
    # The assembler still runs on real independently bound sources; only candidate is altered.
    assembler=rt._assemble_initial_request_038
    for label,mutate in [('false_to_int',lambda v:v['boundaries'].update(ai_enabled=0)),
        ('int_to_float',lambda v:v['materials']['files'][0].update(byte_size=float(v['materials']['files'][0]['byte_size']))),
        ('fact_context',lambda v:v['materials']['fact_snapshot']['inspect_binding'].update(batch_id='OTHER'))]:
        def inconsistent(*a,_mutate=mutate,**k):v=assembler(*a,**k);_mutate(v);return v
        with patched(rt,'_assemble_initial_request_038',inconsistent):request('candidate.'+label,field='initial.request')
    # Actual final-consumption late write; only exact single-file restoration is allowed.
    factfile=leaf.with_name(leaf.name+'.facts')/'fact_packet.json';factraw=factfile.read_bytes();hit={'count':0}
    realio=io.open
    def late_fact(*a,**k):
        v=assembler(*a,**k)
        with realio(factfile,'ab') as f:f.write(b'\n')
        hit['count']+=1;return v
    with patched(rt,'_assemble_initial_request_038',late_fact):request('late.fact',field='facts.fact_packet.json')
    e.check('late.fact_hit',hit['count']==1 and factfile.read_bytes()==factraw+b'\n',hit)
    # Re-read corruption is still rejected; retain original/bad bytes before exact restoration.
    err,_,_=call('late.fact_retained',rt.prepare_runtime_initial_judgment_request,BATCH,leaf,'TECH038-REQUEST\n001',phase='request',history_expectations=empty,**params,field='facts.artifacts')
    for name,raw in [('fact_packet.original.bin',factraw),('fact_packet.late.bin',factfile.read_bytes())]:
        with (out/name).open('xb') as f:f.write(raw)
    factfile.write_bytes(factraw);err,restored,_=request('late.fact_restored');e.check('late.single_restored',err is None and canon(restored)==canon(expected))
    # Frozen history error classes are mapped by identity, with cause/reasons intact.
    loader=rt._load_initial_history_038
    def fail_history(capture):
        h=loader(capture);original=h.inspect_human_initial_judgment_history
        def failed(*a,**k):
            original(*a,**k)
            try:raise OSError('TASK038_CONTROL_HISTORY_IO')
            except OSError as exc:raise h.HumanInitialJudgmentHistoryError('controlled_history_io','TASK038_TEST_INJECTION') from exc
        h.inspect_human_initial_judgment_history=failed;return h
    with patched(rt,'_load_initial_history_038',fail_history):
        err,_,_=request('history.error_mapping',stage='controlled_history_io')
    e.check('history.error_chain',err is not None and err.reasons==['TASK038_TEST_INJECTION'] and any('OSError' in s for s in e.chain_of(err)),e.chain_of(err))
    def block_history(capture):
        h=loader(capture);original=h.inspect_human_initial_judgment_history
        def blocked(*a,**k):
            original(*a,**k);raise h.HumanInitialJudgmentHistoryBlocked('controlled_field','TASK038_TEST_BLOCKED_MAPPING')
        h.inspect_human_initial_judgment_history=blocked;return h
    with patched(rt,'_load_initial_history_038',block_history):err,_,_=request('history.blocked_mapping',field='history.controlled_field')
    e.check('history.blocked_reasons',err.reasons==['TASK038_TEST_BLOCKED_MAPPING'] and err.__cause__.reasons==err.reasons and bool(e.API_RECORDS[-1]['traceback']))
    # Late append uses a complete previously accepted leaf, not a fabricated history result.
    prior_source=ROOT/'data/human_initial_judgment_records/task037_run_01/duplicate_batch/zz_second'
    prior_bytes={p.name:p.read_bytes() for p in prior_source.iterdir()};prior_before={n:sha(b) for n,b in prior_bytes.items()}
    assert len(prior_bytes)==6 and json.loads(prior_bytes['submission.json'])['event_id']=='2'
    appended=namespace/'older_event_2';realmkdir=os.mkdir;hit={'count':0}
    def late_history(*a,**k):
        v=assembler(*a,**k);realmkdir(appended)
        for n,b in prior_bytes.items():
            with realio(appended/n,'xb') as f:f.write(b)
        hit['count']+=1;return v
    with patched(rt,'_assemble_initial_request_038',late_history):request('late.history_append',field='history.expectations.expected_entries')
    e.check('late.history_hit',hit['count']==1 and {p.name:sha(p.read_bytes()) for p in appended.iterdir()}==prior_before,hit)
    request('late.history_retained',field='history.expectations.expected_entries')

    return _finish_history_controls(e,old,out,rt,o,call,leaf,namespace,binding,params,registry)

def _finish_history_controls(e,old,out,rt,o,call,leaf,namespace,binding,params,registry):
    # Shared full/resume suffix. No prerequisite chain is rebuilt.
    prior_source=ROOT/'data/human_initial_judgment_records/task037_run_01/duplicate_batch/zz_second'
    prior_bytes={p.name:p.read_bytes() for p in prior_source.iterdir()};prior_before={n:sha(b) for n,b in prior_bytes.items()}
    appended=namespace/'older_event_2'
    empty={'expectations_version':'TASK-037-human-initial-judgment-history-expectations-1.0','expected_namespace_relative':binding['namespace_relative'],
        'expected_declared_scope':SCOPE,'expected_entries':[]}
    def capture():
        files=own_scene(o.allowed_roots);return {str(ROOT/p):(ROOT/p).read_bytes() for p in files}|{str(p):p.read_bytes() for p in o.allowed_reads}
    source_bytes=capture()
    def request(label,h=empty,**more):return call(label,rt.prepare_runtime_initial_judgment_request,BATCH,leaf,'TECH038-REQUEST\n001',phase='request',history_expectations=h,**params,**more)
    root_api=next(r for r in e.API_RECORDS if r['operation']=='request.empty')
    rootrow=next(r for r in e.CORE_RECORDS if r['caller_api']==root_api['call_id'] and r['core']=='runtime.prepare_runtime_initial_judgment_request')
    direct=[r['core'] for r in e.CORE_RECORDS if r['parent_nested_id']==rootrow['nested_id']]
    counts={key:sum(r['core']==key and r['caller_api']==root_api['call_id'] for r in e.CORE_RECORDS) for key in o.api}
    predicted={'runtime.verify_gate1_effective_approval':6,'runtime.verify_runtime_gate2_decision':5,'runtime.inspect_gate1_approved_load':5,
        'runtime.inspect_gate2_approved_screen':2,'runtime.inspect_gate2_rule_crosscheck':1,'runtime.inspect_gate2_fact_packet':1,
        'facts.render':1,'gate.store.verify':11,'gate.core':11,'source.prepare':6,'history':1}
    nonempty=copy.deepcopy(empty);nonempty['expected_entries']=[{'relative':appended.name,'manifest_file_sha256':sha(prior_bytes['manifest.json'])}]
    new_expected=independent_request(leaf,namespace,params,registry,'TECH038-REQUEST\n001',nonempty,capture())
    err,withhistory,cid=request('request.nonempty',nonempty)
    if err:raise err
    e.check('history.nonempty_complete',canon(withhistory)==canon(new_expected))
    currentrow=next(r for r in e.CORE_RECORDS if r['caller_api']==cid and r['core']=='runtime.prepare_runtime_initial_judgment_request')
    def mutable_ids(v):
        if type(v) not in (dict,list,tuple):return set()
        return {id(v)}|set().union(*(mutable_ids(x) for x in (v.values() if type(v) is dict else v)))
    actual=o.return_refs[currentrow['nested_id']];inputs=set().union(*(mutable_ids(v) for r in e.CORE_RECORDS if r['caller_api']==cid for v in e.CORE_INPUT_REFS[r['nested_id']]))
    e.check('history.nonempty_return_no_alias',not (mutable_ids(actual)&inputs))
    rows=[r for r in e.CORE_RECORDS if r['caller_api']==cid];e.check('history.real_leaf_core',sum(r['core']=='history' for r in rows)==1 and sum(r['core']=='initial.store.verify' for r in rows)==1 and sum(r['core']=='initial.core' for r in rows)==1)
    put(out/'independent_nonempty_request.json',new_expected)
    e.check('history.old_source_unchanged',{p.name:sha(p.read_bytes()) for p in prior_source.iterdir()}==prior_before)
    # One permitted setup save: current-batch synthetic record, using the registered event 1.
    human=read(ROOT/'data/reviews/task034_gpt_20261016_115103/human_initial_judgment_fixture.json')['human_values'];rq=withhistory['request']
    submission={'submission_version':'TASK-034-human-initial-judgment-submission-1.0','event_id':human['event_id'],'batch_id':registry['batch_id'],
        'submission_source':'HUMAN_INITIAL_JUDGMENT','actor':{'actor_kind':'HUMAN_DECLARED','actor_id':human['actor_id'],'declaration_note':human['declaration_note']},
        'decided_at_raw':human['decided_at_raw'],'assessment':human['assessment'],'reason':human['reason'],
        'request_binding':{'request_id':'TECH038-REQUEST\n001','materials_fingerprint':rq['materials']['materials_fingerprint']}}
    initial=load(ROOT/'scripts/store_demo_human_initial_judgment.py','task038_setup_initial_store');o.instrument(initial,'initial_store',[
        ('save_human_initial_judgment_snapshots','initial.store.save'),('verify_human_initial_judgment_snapshots','initial.store.verify')])
    current=namespace/'current_event_1';err,saved,_=call('setup.initial_save',initial.save_human_initial_judgment_snapshots,submission,rq['materials'],rq['expectations'],out_dir=current,
        prior_history=rq['evidence']['history_verification']['prior_history'],phase='setup')
    if err:raise err
    both=copy.deepcopy(nonempty);both['expected_entries']=sorted([*nonempty['expected_entries'],{'relative':current.name,'manifest_file_sha256':sha((current/'manifest.json').read_bytes())}],key=lambda x:x['relative'].encode())
    err,_,cid=request('history.current_batch_rejected',both,field='prior_history.records')
    rows=[r for r in e.CORE_RECORDS if r['caller_api']==cid];e.check('history.current_after_success',sum(r['core']=='initial.store.verify' and r['outcome']=='returned' for r in rows)==2 and sum(r['core']=='history' and r['outcome']=='returned' for r in rows)==1)
    # Preserve a self-consistent leaf with a contradictory declared ancestor; real P1 passes first.
    bad={p.name:read(p) for p in current.iterdir()};bad['prior_history.json']['records'][0]['record_fingerprint']='0'*64
    ph=fp(bad['prior_history.json']);bad['expectations.json']['expected_prior_history_fingerprint']=ph
    bad['judgment_result.json']['record']['history_binding']['prior_history_fingerprint']=ph;bad['judgment_result.json']['record_fingerprint']=fp(bad['judgment_result.json']['record'])
    manifest=bad['manifest.json'];manifest['fingerprints'].update(expectations_fingerprint=fp(bad['expectations.json']),prior_history_fingerprint=ph,record_fingerprint=bad['judgment_result.json']['record_fingerprint'])
    for item in manifest['payloads']:
        b=canon(bad[item['relative']])+b'\n';item.update(file_sha256=sha(b),byte_size=len(b),object_fingerprint=fp(bad[item['relative']]))
    preserve=out/'history_reference_control';preserve.mkdir()
    for n,v in bad.items():
        with (preserve/(n+'.original.bin')).open('xb') as f:f.write((current/n).read_bytes())
        (current/n).write_bytes(canon(v)+b'\n')
    badexpected=copy.deepcopy(both);badexpected['expected_entries'][0]['manifest_file_sha256']=sha((current/'manifest.json').read_bytes())
    err,_,cid=request('history.reference_fp_rejected',badexpected,field='history.entries[0].prior_history.records[0].record_fingerprint')
    rows=[r for r in e.CORE_RECORDS if r['caller_api']==cid];e.check('history.reference_after_real_core',sum(r['core']=='initial.core' and r['outcome']=='returned' for r in rows)==2)
    # Missing declared reference, with all immediate digest dependencies synchronized.
    bad['prior_history.json']['records'][0]['event_id']='ABSENT-REFERENCE';ph=fp(bad['prior_history.json'])
    bad['expectations.json']['expected_prior_history_fingerprint']=ph;bad['judgment_result.json']['record']['history_binding']['prior_history_fingerprint']=ph
    bad['judgment_result.json']['record_fingerprint']=fp(bad['judgment_result.json']['record'])
    manifest['fingerprints'].update(expectations_fingerprint=fp(bad['expectations.json']),prior_history_fingerprint=ph,record_fingerprint=bad['judgment_result.json']['record_fingerprint'])
    for item in manifest['payloads']:
        b=canon(bad[item['relative']])+b'\n';item.update(file_sha256=sha(b),byte_size=len(b),object_fingerprint=fp(bad[item['relative']]))
    for n,v in bad.items():
        with (preserve/(n+'.fp_control.bin')).open('xb') as f:f.write((current/n).read_bytes())
        (current/n).write_bytes(canon(v)+b'\n')
    badexpected['expected_entries'][0]['manifest_file_sha256']=sha((current/'manifest.json').read_bytes())
    request('history.reference_missing',badexpected,field='history.entries[0].prior_history.records[0].event_id')
    put(current/'failure.json',{'test_control':'FAILED_LEAF_NOT_APPROVAL'})
    request('history.failure_priority',badexpected,field='history.entries[0].failure.json')
    factfailure=leaf.with_name(leaf.name+'.facts')/'failure.json'
    put(factfailure,{'failure_version':'TASK-033-fact-packet-failure-1.0','kind':'BLOCKED','stage':'TEST_CONTROL','field':'test_control','reason':'TASK038_TEST_FAILURE_PRIORITY','cause_chain':[]})
    request('facts.failure_priority',badexpected,field='facts.failure')
    # Full registration/profile/parent closure and bounded path scenes are formal payloads.
    labels={};ids={r['nested_id'] for r in e.CORE_RECORDS};apiids={r['call_id'] for r in e.API_RECORDS}
    for row in e.CORE_RECORDS:labels[row['core']]=labels.get(row['core'],0)+1
    e.check('observations.code_closure',labels=={k:v for k,v in o.all_counts().items() if v} and len(ids)==len(e.CORE_RECORDS) and all(r['caller_api'] in apiids and (r['parent_nested_id'] is None or r['parent_nested_id'] in ids) for r in e.CORE_RECORDS),{'entries':labels,'code_profile':o.api})
    e.check('guards.production',not o.hits and not o._other,{'hits':o.hits,'unobserved_entries':o._other})
    put(out/'io_events.json',o.io);put(out/'normal_call_graph.json',{'caller_api':rootrow['caller_api'],'counts':counts,'direct':direct,'predicted':predicted})
    put(out/'source_buffers_identity.json',{p:{'byte_size':len(b),'sha256':sha(b)} for p,b in source_bytes.items()})
    return o,{'profile':{'registry_keys':14,'code_entries':17,'gate1_materials':38},'one_prerequisite_chain':True,'guard_proof':o.proof,
        'normal_request_code_counts':counts,'historical_namespace_source':str(prior_source),'source_namespace_was_not_declared_valid':True,
        'not_executed':{'physical_junction':{'count':None,'reason':'existing permission limitation; no retry'},'real_approval':None,'real_initial_judgment':None,
            'initial_runtime_save':None,'AI':None,'old_tests':None,'receiver_subprocess':None},'direct_checker_cli':{'count':0,'reason':'read-only reuse of accepted batch'}}

class Observer:
    def __init__(self,rt,e,old):
        self.rt,self.e,self.old=rt,e,old;self.codes={};self.originals=[];self.marked=set();self.modules=[];self.labels={}
        self.api={};self.count=0;self.normalizer=self.loader=None;self._other={};self.stack=[];self.serial=0;self.phase='setup';self.io=[];self.hits=[];self.proof=[]
        self.allowed_reads=set();self.allowed_roots=[];self.allowed_write_roots=[];self.return_refs={};self.prefix_api={};self.prefix_source=None
        for n in BUSINESS:self.wrap(rt,n,'runtime.'+n)
        for loader,kind,entries in (
            ('_load_frozen_prepare','source',[('prepare_human_gate1_request','source.prepare')]),
            ('_load_frozen_store','gate_store',[('save_human_gate_decision_snapshots','gate.store.save'),('verify_human_gate_decision_snapshots','gate.store.verify')]),
            ('_load_frozen_normalizer','plain',[('normalize_workbook','algorithm.normalize')]),
            ('_load_frozen_sqlite_core','plain',[('load_normalized_to_sqlite','algorithm.load')]),
            ('_load_frozen_screen_031','plain',[('screen_sqlite','algorithm.screen')]),
            ('_load_frozen_crosscheck_032','plain',[('verify_rule_facts','algorithm.crosscheck')]),
            ('_load_frozen_facts_033','plain',[('build_fact_packet','algorithm.facts_build'),('render_markdown','facts.render')]),
            ('_load_initial_history_038','history',[('inspect_human_initial_judgment_history','history')])):
            original=getattr(rt,loader)
            def observed_loader(*a,_original=original,_kind=kind,_entries=entries,**k):
                m=_original(*a,**k);self.instrument(m,_kind,_entries);return m
            setattr(rt,loader,observed_loader)
    def all_counts(self):
        return {k:self.api.get(k,0)+self.prefix_api.get(k,0) for k in self.api.keys()|self.prefix_api.keys()}
    def points(self,refs):
        return [{'reference_id':id(v),'snapshot':self.describe(copy.deepcopy(v)),'fingerprint':fp(self.describe(v))} for v in refs]
    def describe(self,v):
        if isinstance(v,Path):return {'$path':str(v)}
        if type(v) in (list,tuple):return [self.describe(x) for x in v]
        if type(v) is dict:return {k:self.describe(x) for k,x in v.items()}
        return self.old.evidence_value(v)
    def instrument(self,m,kind,entries):
        key=(id(m),kind)
        if key in self.marked:return
        self.marked.add(key);self.modules.append(m)
        for n,label in entries:self.wrap(m,n,label)
        if kind in ('gate_store','initial_store'):
            loader='_core' if kind=='gate_store' else '_load_core';original=getattr(m,loader)
            def core_load(*a,**k):
                c=original(*a,**k);fn='build_human_gate_decision_record' if kind=='gate_store' else 'build_human_initial_judgment_record'
                self.instrument(c,'plain',[(fn,'gate.core' if kind=='gate_store' else 'initial.core')]);return c
            setattr(m,loader,core_load)
        elif kind=='history':
            original=m._load_store
            def store_load(*a,**k):
                s,b=original(*a,**k);self.instrument(s,'initial_store',[
                    ('save_human_initial_judgment_snapshots','initial.store.save'),('verify_human_initial_judgment_snapshots','initial.store.verify')]);return s,b
            m._load_store=store_load
    def wrap(self,m,n,label):
        fn=getattr(m,n);self.originals.append(fn);self.codes[id(fn.__code__)]=label;self.api.setdefault(label,0)
        def observed(*a,**k):
            if self.phase=='request' and (label.startswith('algorithm.') or '.save' in label or label.startswith('runtime.run_') or label in ('runtime.build_runtime_registry','runtime.prepare_runtime_gate1_request','runtime.prepare_runtime_gate2_request')):
                self.hits.append('forbidden_entry:'+label);raise AssertionError('TASK038_FORBIDDEN:'+label)
            cid=self.e.CALL_STACK[-1];self.serial+=1;nid=f'entry_{self.serial:05d}';refs=[*a,*k.values()]
            self.e.CORE_INPUT_REFS[nid]=refs
            row={'nested_id':nid,'core':label,'caller_api':cid,'parent_nested_id':self.stack[-1] if self.stack else None,
                'phase':self.phase,'args':self.describe(a),'kwargs':self.describe(k),'input_refs_before':self.points(refs)}
            self.stack.append(nid)
            try:
                result=fn(*a,**k);self.return_refs[nid]=result;row.update(outcome='returned',**{'return':copy.deepcopy(result)});return result
            except Exception as exc:
                row.update(outcome='exception',exception_type=type(exc).__name__,exception_str=str(exc),field=getattr(exc,'field',None),stage=getattr(exc,'stage',None),
                    reasons=copy.deepcopy(getattr(exc,'reasons',None)),traceback=traceback.format_exc(),cause_chain=self.e.chain_of(exc));raise
            finally:self.stack.pop();row['input_refs_after']=self.points(refs);self.e.CORE_RECORDS.append(row)
        setattr(m,n,observed)
    def profile(self,frame,event,arg):
        if event!='call':return
        label=self.codes.get(id(frame.f_code))
        if label:self.api[label]+=1;self.count+=1
        elif frame.f_code.co_name in {'check_dev_action','build_initial_judgment_record','export_dev_review_bundle','run_demo_workflow','build_human_initial_judgment_record','build_human_gate_decision_record'} and str(Path(frame.f_code.co_filename).absolute()).startswith(str(ROOT/'scripts')):
            self._other[frame.f_code.co_name]=self._other.get(frame.f_code.co_name,0)+1
    @contextmanager
    def guard(self,prove=False):
        request=self.phase=='request';saved=[]
        def replace(obj,n,fn):saved.append((obj,n,getattr(obj,n)));setattr(obj,n,fn)
        def deny(name):
            def no(*a,**k):(self.proof if prove else self.hits).append(name);raise AssertionError('TASK038_DENIED:'+name)
            return no
        def opened(original):
            def call(path,mode='r',*a,**k):
                p=Path.cwd()/Path(path);writing=any(x in mode for x in 'wax+')
                allowed=(not request and any(p.is_relative_to(r) for r in self.allowed_write_roots)) if writing else (p in self.allowed_reads or any(p.is_relative_to(r) for r in self.allowed_roots))
                if not allowed:return deny('write' if writing else 'read')()
                self.io.append({'path':str(p),'mode':mode,'writing':writing,'phase':self.phase,'call_id':self.e.CALL_STACK[-1] if self.e.CALL_STACK else None})
                return original(path,mode,*a,**k)
            return call
        try:
            replace(builtins,'open',opened(builtins.open));replace(io,'open',opened(io.open));replace(socket,'socket',deny('network'));replace(subprocess,'Popen',deny('subprocess'))
            if request:
                replace(os,'open',deny('os.open'))
                for n in ('mkdir','unlink','remove','rmdir','rename','replace'):replace(os,n,deny('filesystem_mutation.'+n))
                dt=datetime.datetime
                class NoNow(dt):now=classmethod(deny('clock'));utcnow=classmethod(deny('clock'));today=classmethod(deny('clock'))
                replace(datetime,'datetime',NoNow);replace(self.rt,'datetime',NoNow)
                for m in self.modules:
                    if hasattr(m,'datetime') and isinstance(m.datetime,type):replace(m,'datetime',NoNow)
                for obj,n in ((random,'random'),(random,'getrandbits'),(secrets,'token_bytes'),(uuid,'uuid4'),(os,'urandom')):replace(obj,n,deny('random'))
                original_connect=sqlite3.connect
                def connect(database,*a,**k):
                    if not k.get('uri') or 'mode=ro' not in str(database):return deny('sqlite_write_connection')()
                    return original_connect(database,*a,**k)
                replace(sqlite3,'connect',connect)
            yield
        finally:
            for obj,n,fn in reversed(saved):setattr(obj,n,fn)

def run(e,old,out,prepare_only=False,resume_prefix=None):
    rt=load(RUNTIME,'task038_runtime_under_test');o=Observer(rt,e,old);e.jsonable=o.describe;e.core_input_point=o.points
    chain_name=resume_prefix.name if resume_prefix else out.name
    runtime=ROOT/'data/runtime'/chain_name;g1=ROOT/'data/human_gate_decision_records/gate1'/chain_name
    g2=ROOT/'data/human_gate_decision_records/gate2'/chain_name;dbroot=ROOT/'data/sqlite_tests'/chain_name;histroot=ROOT/'data/human_initial_judgment_records'/chain_name
    if not resume_prefix:
        for p in (runtime,g1,dbroot,histroot):p.mkdir(parents=True,exist_ok=False)
    namespace=histroot/'bound'
    if not resume_prefix:namespace.mkdir()
    leaf=runtime/'normal';scope=g1/'normal';event=scope/'event_0001';event2=g2/'normal'/'event_0001'
    binding={'namespace_relative':namespace.relative_to(ROOT).as_posix(),'declared_scope':SCOPE}
    o.allowed_roots=[BATCH,runtime,g1,g2,dbroot,histroot];o.allowed_write_roots=[runtime,g1,g2,dbroot,histroot]
    prep=rt._load_frozen_prepare();o.allowed_reads={ROOT/p for _,p in prep.PROJECT_MATERIAL_FILES}|{RUNTIME,ROOT/'scripts/prepare_demo_human_gate1.py'}|{ROOT/p for p in rt.INITIAL_COMPONENT_SHA256}
    o.allowed_reads.update(ROOT/'docs/proposals'/name for name in ('HUMAN_GATE_DECISION_PROTOCOL_V1_DRAFT.md','HUMAN_GATE_DECISION_CASES_V1_DRAFT.md'))
    sources=read(ROOT/'data/runtime_initial_judgment_request_tests/task038_prepare_01/starting_identity.json')['identities']
    for p,v in sources.items():
        if p!='scripts/runtime_gate1.py':assert identity(ROOT/p)==v
    gate_fields=read(ROOT/'data/decision_protocol_checks/task020r2_run_01/fixture_values.json')
    def call(label,fn,*a,phase='setup',field=None,stage=None,**k):
        oldphase=o.phase;o.phase=phase;before=dict(o.api);points=o.points([*a,*k.values()]);scene_before=own_scene(o.allowed_roots)
        def guarded(*args,**kwargs):
            with o.guard():return fn(*args,**kwargs)
        try:err,value,cid=e.call_api(rt,label,guarded,*a,**k)
        finally:o.phase=oldphase
        delta={key:o.api[key]-before.get(key,0) for key in o.api}
        e.API_RECORDS[-1].update(record_category=phase,actual_entries=delta,reasons=copy.deepcopy(getattr(err,'reasons',None)),
            input_refs_before=points,input_refs_after=o.points([*a,*k.values()]),input_refs_api_end=o.points([*a,*k.values()]),
            path_scene_before=scene_before,path_scene_api_end=own_scene(o.allowed_roots))
        ok=isinstance(err,rt.RuntimeGate1Blocked) and err.field==field if field else (isinstance(err,rt.RuntimeGate1Error) and err.stage==stage if stage else err is None)
        e.check(label,ok,{'call_id':cid,'field':getattr(err,'field',None),'stage':getattr(err,'stage',None),'type':type(err).__name__,'delta':delta})
        print(json.dumps({'operation':label,'ok':ok,'field':getattr(err,'field',None),'stage':getattr(err,'stage',None)}),flush=True)
        return err,value,cid
    sys.setprofile(o.profile)
    try:
        if resume_prefix:
            partial=read(resume_prefix/'process_exception.json')
            if 'capture_file() missing' not in partial['traceback']:raise AssertionError('unexpected checkpoint failure')
            for target,key in ((e.API_RECORDS,'API_records'),(e.CORE_RECORDS,'nested_records')):target.extend(copy.deepcopy(partial[key]))
            e.COUNTER['value']=max(int(r['call_id'].split('_')[-1]) for r in e.API_RECORDS)
            o.serial=max(int(r['nested_id'].split('_')[-1]) for r in e.CORE_RECORDS)
            o.prefix_api=copy.deepcopy(partial['actual_code_entries']);o.prefix_source={'path':str(resume_prefix/'process_exception.json'),'identity':identity(resume_prefix/'process_exception.json'),
                'API_records':len(e.API_RECORDS),'observed_entries':len(e.CORE_RECORDS),'note':'prior segment real observations; NOT new calls in this process; no original checks recovered or overwritten'}
            for name in ('profile.json','independent_empty_request.json'):
                with (out/name).open('xb') as f:f.write((resume_prefix/name).read_bytes())
            with (out/'prior_segment.source.bin').open('xb') as f:f.write((resume_prefix/'process_exception.json').read_bytes())
            registry=read(resume_prefix/'profile.json')['registry']
            params={'scope_dir':scope,'event_relative':event.relative_to(ROOT).as_posix(),'database_path':dbroot/'normal'/'runtime.sqlite3','gate2_event_relative':event2.relative_to(ROOT).as_posix()}
            validate_prefix(e,rt,out,resume_prefix,registry,o)
            prove_guard(e,o,leaf)
            result,extra=_finish_history_controls(e,old,out,rt,o,call,leaf,namespace,binding,params,registry)
            extra['observation_segments']={'prior':o.prefix_source,'new_API_calls':len(e.API_RECORDS)-o.prefix_source['API_records'],'new_original_code_entries':copy.deepcopy(o.api),
                'aggregate_original_code_entries':o.all_counts(),'no_rebuilt_chain':True}
            return result,extra
        err,registry,_=call('setup.registry',rt.build_runtime_registry,BATCH,leaf,scope_dir=scope,initial_judgment_history=binding)
        if err:raise err
        err,req1,_=call('setup.gate1_request',rt.prepare_runtime_gate1_request,BATCH,leaf,'FIXTURE-REQ-G1-0001')
        if err:raise err
        registry=registry['registry'];m1=req1['request']['materials']
        e.check('profile.counts',len(registry)==14 and len(registry['code_manifest']['entries'])==17 and len(m1['files'])==38)
        e.check('profile.registry_file_bound',next(x for x in m1['files'] if x['relative']=='runtime/runtime_registry.json')==
            {'relative':'runtime/runtime_registry.json','byte_size':(leaf/'runtime_registry.json').stat().st_size,'file_sha256':sha((leaf/'runtime_registry.json').read_bytes())})
        # Full expectations from frozen predecessor lists + explicit TASK-038 additions.
        old_source=ROOT/'data/runtime_initial_judgment_request_tests/task038_prepare_01/runtime.before.bin'
        codepaths=sorted((*literal(old_source,'CODE_FILES'),'scripts/build_demo_human_initial_judgment.py','scripts/store_demo_human_initial_judgment.py',
            'scripts/inspect_demo_human_initial_judgment_history.py','scripts/runtime_gate1.py'),key=lambda x:x.encode())
        code={'manifest_version':'TASK-038-code-manifest-1.0','entries':[{'relative':p,'file_sha256':identity(ROOT/p)['sha256']} for p in codepaths]}
        rules={'version':'TASK-006-rule-core-1.1','entries':[{'rule_id':'R0'+str(i),'rule_version':f'TASK-006-R0{i}-1.0','relative':f'sql/rules/r0{i}.sql','file_sha256':identity(ROOT/f'sql/rules/r0{i}.sql')['sha256']} for i in range(1,5)]}
        sourcefiles=[{'relative':'batch/'+p,'file_sha256':identity(BATCH/p)['sha256'],'byte_size':identity(BATCH/p)['byte_size']} for p in literal(old_source,'BATCH_FILES')]
        sourcefiles.sort(key=lambda x:x['relative'].encode());projectfiles={p for _,p in prep.PROJECT_MATERIAL_FILES}|{'scripts/runtime_gate1.py'}|set(rt.INITIAL_COMPONENT_SHA256)
        material_files=sourcefiles+[{'relative':'project/'+p,'file_sha256':identity(ROOT/p)['sha256'],'byte_size':identity(ROOT/p)['byte_size']} for p in projectfiles]
        material_files.append({'relative':'runtime/runtime_registry.json','file_sha256':identity(leaf/'runtime_registry.json')['sha256'],'byte_size':identity(leaf/'runtime_registry.json')['byte_size']})
        material_files.sort(key=lambda x:x['relative'].encode())
        cfg=identity(ROOT/'config/human_flow_v1.json')['sha256'];inp=identity(BATCH/'source/input.xlsx');contract={'contract_effective':True,'contract_version':'V1','contract_file_sha256':'174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad'}
        run_expected={'code':{'file_sha256':identity(RUNTIME)['sha256'],'manifest_fingerprint':fp(code)},'rules':{'version':rules['version'],'manifest_fingerprint':fp(rules)},'config':{'file_sha256':cfg},'input':{'file_sha256':inp['sha256']}}
        registry_expected={'registry_version':'TASK-038-runtime-registry-1.0','batch_id':read(BATCH/'batch_manifest.json')['batch_id'],'registered_at':registry['registered_at'],
            'scope_ref':scope.relative_to(ROOT).as_posix(),'batch_files':sourcefiles,'code_manifest':code,'rules_manifest':rules,'config':{'config_ref':'config/human_flow_v1.json','file_sha256':cfg},
            'input':{'input_ref':'batch/source/input.xlsx','file_sha256':inp['sha256'],'byte_size':inp['byte_size']},'contract':contract,'run_binding':run_expected,
            'run_binding_sha256':fp(run_expected),'note':'RUNTIME_REGISTRATION_ONLY: not a decision, not an approval, not an execution permission','initial_judgment_history':binding}
        material_expected={'gate':'GATE1','batch_id':registry_expected['batch_id'],'run_binding':run_expected,'contract_binding':contract,'files':material_files,
            'quality':{'status':'OK','structural_blockers':[],'quality_blockers':[],'verification_failures':[]}}
        material_expected['materials_fingerprint']=fp(material_expected)
        e.check('profile.complete_registry',canon(registry)==canon(registry_expected),{'technical_time_source':'actual_program_registration_not_human_decision','expected':registry_expected})
        e.check('profile.complete_gate1_materials',canon(m1)==canon(material_expected),{'independently_read_files':38,'expected':material_expected})
        put(out/'profile.json',{'registry':registry,'gate1_request':req1})
        if prepare_only:return o,{'preflight_only':True,'actual_code_entries':o.api}
        # Before Gate1, a domain-only changed copy passes the actual public read API.
        alternate=histroot/'alternate';alternate.mkdir();clone=runtime/'alternate_registry';clone.mkdir()
        changed=copy.deepcopy(registry);changed['initial_judgment_history']['namespace_relative']=alternate.relative_to(ROOT).as_posix()
        rb=read(leaf/'runtime_registry_readback.json');raw=canon(changed)+b'\n';rb.update(registry_sha256=fp(changed),registry_file_sha256=sha(raw),registry_byte_size=len(raw))
        with (clone/'runtime_registry.json').open('xb') as f:f.write(raw)
        put(clone/'runtime_registry_readback.json',rb)
        err,clone_read,_=call('profile.changed_domain_public_read',rt.read_runtime_registry,clone,phase='diagnostic')
        if err:raise err
        e.check('profile.domain_only_copy',canon(clone_read['registry'])==canon(changed) and {k:v for k,v in changed.items() if k!='initial_judgment_history'}=={k:v for k,v in registry.items() if k!='initial_judgment_history'})
        sub1=copy.deepcopy(gate_fields['BASE1']['submission']);sub1['batch_id']=registry['batch_id']
        sub1['request_binding']={'request_id':'FIXTURE-REQ-G1-0001','materials_binding':m1['materials_fingerprint']}
        err,r1,_=call('setup.gate1_save',rt.save_runtime_gate1_decision,BATCH,leaf,'FIXTURE-REQ-G1-0001',sub1,event,scope_dir=scope)
        if err:raise err
        params={'scope_dir':scope,'event_relative':event.relative_to(ROOT).as_posix(),'database_path':dbroot/'normal'/'runtime.sqlite3'}
        err,_,_=call('setup.load',rt.run_gate1_approved_load,BATCH,leaf,**params)
        if err:raise err
        err,req2,_=call('setup.gate2_request',rt.prepare_runtime_gate2_request,BATCH,leaf,'FIXTURE-REQ-G2-0001',**params)
        if err:raise err
        sub2=copy.deepcopy(gate_fields['BASE2']['submission']);sub2['batch_id']=registry['batch_id']
        sub2['request_binding']={'request_id':'FIXTURE-REQ-G2-0001','materials_binding':req2['request']['materials']['materials_fingerprint']}
        sub2['prior_decision_binding']={'wrapper_version':rt.GATE2_WRAPPER_VERSION,'record':r1['record'],'record_fingerprint':r1['record_fingerprint']}
        err,_,_=call('setup.gate2_save',rt.save_runtime_gate2_decision,BATCH,leaf,'FIXTURE-REQ-G2-0001',sub2,event2,**params)
        if err:raise err
        params['gate2_event_relative']=event2.relative_to(ROOT).as_posix()
        for label,fn in (('screen',rt.run_gate2_approved_screen),('crosscheck',rt.run_gate2_rule_crosscheck),('facts',rt.run_gate2_fact_packet)):
            err,_,_=call('setup.'+label,fn,BATCH,leaf,**params)
            if err:raise err
        # Remaining finite controls reuse this one prerequisite chain.
        return _request_controls(e,old,out,rt,o,call,leaf,namespace,binding,params,registry,gate_fields)
    except Exception:
        put(out/'process_exception.json',{'traceback':traceback.format_exc(),'API_records':e.API_RECORDS,'nested_records':e.CORE_RECORDS,'actual_code_entries':o.api})
        raise
    finally:sys.setprofile(None)

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--out-dir',required=True);p.add_argument('--prepare-only',action='store_true');p.add_argument('--replay');p.add_argument('--resume-prefix');p.add_argument('--mutate',choices=('none','candidate-return','ledger-late','checks-late'),default='none')
    a=p.parse_args(argv);out=Path(a.out_dir).resolve()
    if out==TEST_ROOT or not out.is_relative_to(TEST_ROOT) or out.exists() or not out.name.startswith('task038_'):raise SystemExit('fresh task038_ strict descendant required')
    old=load(ROOT/'tests/test_build_demo_human_initial_judgment.py','task038_readonly_short_helpers');e=old.evidence_module();e.ROUND['id']=out.name
    original=e.build_candidate
    def build(*args,**k):
        c=original(*args,**k);c['summary']['task']='TASK-038';obs=args[1]
        c['summary']['observed']={'actual_code_entries':obs.all_counts() if obs else None,'new_process_code_entries':obs.api if obs else None,'prior_segment':obs.prefix_source if obs else None,'replay_observations_are_new_calls':False if not obs else None}
        c['summary']['record_categories']={role:sum(x.get('record_category')==role for x in c['api_records']) for role in ('setup','request','diagnostic')};return c
    e.build_candidate=build;out.mkdir(parents=True,exist_ok=False)
    if a.replay:
        src=Path(a.replay).resolve()
        if not src.is_relative_to(TEST_ROOT) or src==out:raise SystemExit('invalid replay source')
        checkpoint=read(src/'expected_observations.json');o=None;extra={'replay_only':True,'source':str(src)}
    else:
        if a.mutate!='none':raise SystemExit('mutate requires replay')
        resume=Path(a.resume_prefix).resolve() if a.resume_prefix else None
        if resume and (not resume.is_relative_to(TEST_ROOT) or resume==out):raise SystemExit('invalid continuation source')
        o,extra=run(e,old,out,a.prepare_only,resume);checkpoint=e.freeze_expectations()
    real=Path.read_bytes;control={'hits':0}
    if a.mutate.endswith('-late'):
        def reader(path):
            raw=real(path);frame=sys._getframe(1)
            if frame.f_code is e.finish.__code__ and 'terminal_buffers' in frame.f_locals and path==out/'expected_observations.json' and not control['hits']:
                target=out/('file_ledger.json' if a.mutate=='ledger-late' else 'checks.json');before=real(target)
                with target.open('ab') as f:f.write(b'\n')
                control.update(hits=1,target=target.name,before_size=len(before),after_size=len(before)+1,before_sha256=sha(before),after_sha256=sha(before+b'\n'))
            return raw
        Path.read_bytes=reader
    try:code=e.finish(out,checkpoint,'candidate-return' if a.mutate=='candidate-return' else 'none',o,extra)
    finally:Path.read_bytes=real
    if a.mutate.endswith('-late'):put(out/'control_observation.json',control)
    return code
if __name__=='__main__':raise SystemExit(main())
