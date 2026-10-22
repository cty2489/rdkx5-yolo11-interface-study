"""ctypes access to the same C SDK bridge for all three independent modes."""
import ctypes as C
import numpy as np
from consumer import check_abi

class Property(C.Structure):
    _fields_=[('name',C.c_char*64),('type',C.c_int32),('layout',C.c_int32),('dimensions',C.c_int32),
              ('valid',C.c_int32*8),('aligned',C.c_int32*8),('stride',C.c_int32*8),('bytes',C.c_int32),
              ('quanti_type',C.c_int32),('axis',C.c_int32),('scale_len',C.c_int32),
              ('shift_len',C.c_int32),('zero_len',C.c_int32),('scale_bits',C.c_uint32)]
assert C.sizeof(Property)==200

class SDK:
    def __init__(self,library,model,strategy):
        self.lib=C.CDLL(str(library));self.ctx=C.c_void_p();self.strategy=strategy
        specifications={
           'p1_open':([C.c_char_p,C.POINTER(C.c_void_p)],C.c_int),
           'p1_close':([C.c_void_p],C.c_int),
           'p1_get_property':([C.c_void_p,C.c_int,C.POINTER(Property)],C.c_int),
           'p1_prepare':([C.c_void_p,C.c_void_p,C.c_size_t],C.c_int),
           'p1_forward':([C.c_void_p],C.c_int),
           'p1_output_pointer':([C.c_void_p,C.c_int],C.c_void_p),
           'p1_forward_attempts':([C.c_void_p],C.c_uint64),
           'p1_forward_completions':([C.c_void_p],C.c_uint64),
           'p1_sdk_version':([],C.c_char_p),
           'p1_output_count':([C.c_void_p],C.c_int),
           'p1_layout_nhwc':([],C.c_int),
           'p1_layout_nchw':([],C.c_int)}
        for name,(args,res) in specifications.items():
            f=getattr(self.lib,name);f.argtypes=args;f.restype=res
        self.checked(self.lib.p1_open(str(model).encode(),C.byref(self.ctx)))
        self.props={};self.indices={}
        try:
            count=self.lib.p1_output_count(self.ctx)
            if count!=(6 if strategy=='M6' else 9):raise ValueError('Wrong actual output count')
            nhwc=self.lib.p1_layout_nhwc();nchw=self.lib.p1_layout_nchw()
            for index in range(count):
                p=Property();self.checked(self.lib.p1_get_property(self.ctx,index,C.byref(p)))
                name=p.name.decode();n=p.dimensions
                prop={'name':name,'dtype':{11:'INT16',13:'FLOAT32'}.get(p.type,'OTHER'),
                      'layout':p.layout,'validShape':list(p.valid)[:n],'alignedShape':list(p.aligned)[:n],
                      'stride':list(p.stride),'alignedByteSize':p.bytes,'quantiType':p.quanti_type,
                      'quantizeAxis':p.axis,'scaleLen':p.scale_len,'scaleFp32Bits':[p.scale_bits] if p.scale_len else [],
                      'shiftLen':p.shift_len,'zeroPointLen':p.zero_len}
                prop['layoutName']='NHWC' if p.layout==nhwc else ('NCHW' if p.layout==nchw else 'OTHER')
                if strategy in ['CID_MAX','CID_INDEX']:
                    shape=prop['validShape']
                    if len(shape)!=4 or shape[0]!=1 or prop['dtype']!='FLOAT32':raise ValueError('Unverified CID FLOAT32 ABI')
                    if p.layout==nchw:channels,h,w=shape[1:]
                    elif p.layout==nhwc:h,w,channels=shape[1:]
                    else:raise ValueError('Unsupported declared CID layout')
                    if h!=w or h not in [80,40,20] or channels not in [64,80,1]:raise ValueError('Unverified CID shape')
                    head=[80,40,20].index(h);role={64:'bbox',80:'cls',1:'class'}[channels]+str(head)
                elif strategy=='M6':
                    shape=prop['validShape']
                    if p.layout!=nhwc or len(shape)!=4 or shape[0]!=1 or shape[1]!=shape[2] or shape[1] not in [80,40,20] or shape[3] not in [64,80] or prop['dtype']!='FLOAT32':raise ValueError('Unverified M6 NHWC ABI')
                    head=[80,40,20].index(shape[1]);role=('bbox' if shape[3]==64 else 'cls')+str(head)
                else:role=name
                if role in self.props:raise ValueError('Duplicate semantic output')
                self.props[role]=prop;self.indices[role]=index
            if strategy in ['CID_MAX','CID_INDEX']:
                if set(self.props)!={f'{k}{i}' for i in range(3) for k in ['bbox','cls','class']}:raise ValueError('Incomplete CID output roles')
                for q in self.props.values():
                    if q['stride'][3]!=4 or sum((z-1)*v for z,v in zip(q['validShape'],q['stride']))+4>q['alignedByteSize']:raise ValueError('CID allocation/stride mismatch')
            elif strategy=='M6':
                if set(self.props)!={f'{k}{i}' for i in range(3) for k in ['bbox','cls']}:raise ValueError('Incomplete M6 output roles')
                for q in self.props.values():
                    if q['stride'][3]!=4 or sum((z-1)*v for z,v in zip(q['validShape'],q['stride']))+4>q['alignedByteSize']:raise ValueError('M6 allocation/stride mismatch')
            else:check_abi(self.props,strategy)
        except BaseException:
            self.close();raise
    @staticmethod
    def checked(rc):
        if rc:raise RuntimeError(f'C SDK bridge error {rc}')
    def prepare(self,raw):
        if len(raw)!=614400:raise ValueError('Wrong fixed NV12 frame bytes')
        pointer=C.c_char_p(raw)
        self.checked(self.lib.p1_prepare(self.ctx,pointer,len(raw)))
    def forward(self):self.checked(self.lib.p1_forward(self.ctx))
    def outputs(self):
        views={}
        for name,p in self.props.items():
            pointer=self.lib.p1_output_pointer(self.ctx,self.indices[name])
            if not pointer:raise RuntimeError('Null SDK output')
            buffer=(C.c_uint8*p['alignedByteSize']).from_address(pointer)
            views[name]=np.ndarray(tuple(p['validShape']),dtype='<i2' if p['dtype']=='INT16' else '<f4',
                                   buffer=buffer,strides=tuple(p['stride'][:4]))
        return views
    def timing(self):
        names=['SDKCopy_ms','SDKClean_ms','SDKSubmit_ms','SDKWait_ms','SDKInvalidate_ms','SDKRelease_ms']
        if not hasattr(self.lib,'p1_get_timing'):return {}
        fn=self.lib.p1_get_timing;fn.argtypes=[C.c_void_p,C.POINTER(C.c_uint64)];fn.restype=C.c_int
        values=(C.c_uint64*6)();self.checked(fn(self.ctx,values))
        return {k:int(v)/1e6 for k,v in zip(names,values)}
    def counts(self):
        return {'forward_attempts':int(self.lib.p1_forward_attempts(self.ctx)),
                'forward_completions':int(self.lib.p1_forward_completions(self.ctx))}
    def close(self):
        if self.ctx.value:
            ctx=self.ctx;self.ctx=C.c_void_p();self.checked(self.lib.p1_close(ctx))
