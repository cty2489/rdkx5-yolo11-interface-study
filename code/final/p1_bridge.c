/* Thin, shared SDK bridge. Model/buffers loaded once per independent process.
 * No fast-math, model compilation, global setting changes or benchmark loop.
 */
#include <dnn/hb_dnn.h>
#include <dnn/hb_sys.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  hbPackedDNNHandle_t packed;
  hbDNNHandle_t handle;
  hbDNNTensor input,outputs[9];
  int allocated_input,allocated_outputs;
  uint64_t attempted_forwards,completed_forwards;
} P1Context;

typedef struct {
  char name[64];
  int32_t type,layout,dimensions,valid[8],aligned[8],stride[8],bytes;
  int32_t quanti_type,axis,scale_len,shift_len,zero_len;
  uint32_t scale_bits;
} P1Property;

int p1_close(P1Context *ctx) {
  if(!ctx)return 0;
  int failure=0,rc;
  if(ctx->allocated_input){rc=hbSysFreeMem(&ctx->input.sysMem[0]);if(rc)failure=rc;}
  for(int i=0;i<ctx->allocated_outputs;i++){rc=hbSysFreeMem(&ctx->outputs[i].sysMem[0]);if(rc)failure=rc;}
  if(ctx->packed){rc=hbDNNRelease(ctx->packed);if(rc)failure=rc;}
  free(ctx);return failure;
}

int p1_open(const char *model,P1Context **returned) {
  if(!model||!returned)return -201;
  *returned=NULL;
  P1Context *ctx=calloc(1,sizeof(*ctx));if(!ctx)return -202;
  int rc,count,inputs,outputs;const char **names;
#define CALL_OR_FAIL(call) do{rc=(call);if(rc)goto fail;}while(0)
  const char *models[]={model};
  CALL_OR_FAIL(hbDNNInitializeFromFiles(&ctx->packed,models,1));
  CALL_OR_FAIL(hbDNNGetModelNameList(&names,&count,ctx->packed));
  if(count!=1){rc=-203;goto fail;}
  CALL_OR_FAIL(hbDNNGetModelHandle(&ctx->handle,ctx->packed,names[0]));
  CALL_OR_FAIL(hbDNNGetInputCount(&inputs,ctx->handle));
  CALL_OR_FAIL(hbDNNGetOutputCount(&outputs,ctx->handle));
  if(inputs!=1||outputs!=9){rc=-204;goto fail;}
  CALL_OR_FAIL(hbDNNGetInputTensorProperties(&ctx->input.properties,ctx->handle,0));
  if(ctx->input.properties.tensorType!=HB_DNN_IMG_TYPE_NV12 || ctx->input.properties.alignedByteSize!=614400){rc=-205;goto fail;}
  CALL_OR_FAIL(hbSysAllocCachedMem(&ctx->input.sysMem[0],614400));ctx->allocated_input=1;
  for(int i=0;i<9;i++) {
    CALL_OR_FAIL(hbDNNGetOutputTensorProperties(&ctx->outputs[i].properties,ctx->handle,i));
    CALL_OR_FAIL(hbSysAllocCachedMem(&ctx->outputs[i].sysMem[0],ctx->outputs[i].properties.alignedByteSize));ctx->allocated_outputs++;
    memset(ctx->outputs[i].sysMem[0].virAddr,0,ctx->outputs[i].properties.alignedByteSize);
    CALL_OR_FAIL(hbSysFlushMem(&ctx->outputs[i].sysMem[0],HB_SYS_MEM_CACHE_CLEAN));
  }
  *returned=ctx;return 0;
fail:p1_close(ctx);return rc;
#undef CALL_OR_FAIL
}

int p1_get_property(P1Context *ctx,int index,P1Property *out) {
  if(!ctx||!out||index<0||index>=9)return -210;
  const char *name=NULL;int rc=hbDNNGetOutputName(&name,ctx->handle,index);if(rc)return rc;
  const hbDNNTensorProperties *p=&ctx->outputs[index].properties;
  if(strlen(name)>=sizeof(out->name)||p->validShape.numDimensions>8)return -211;
  memset(out,0,sizeof(*out));strcpy(out->name,name);
  out->type=p->tensorType;out->layout=p->tensorLayout;out->dimensions=p->validShape.numDimensions;
  for(int j=0;j<8;j++){
    out->valid[j]=p->validShape.dimensionSize[j];out->aligned[j]=p->alignedShape.dimensionSize[j];out->stride[j]=p->stride[j];
  }
  out->bytes=p->alignedByteSize;out->quanti_type=p->quantiType;out->axis=p->quantizeAxis;
  out->scale_len=p->scale.scaleLen;out->shift_len=p->shift.shiftLen;out->zero_len=p->scale.zeroPointLen;
  if(p->scale.scaleLen==1)memcpy(&out->scale_bits,p->scale.scaleData,sizeof(out->scale_bits));
  return 0;
}

int p1_prepare(P1Context *ctx,const void *bytes,size_t length) {
  if(!ctx||!bytes||length!=614400)return -220;
  memcpy(ctx->input.sysMem[0].virAddr,bytes,length);
  return hbSysFlushMem(&ctx->input.sysMem[0],HB_SYS_MEM_CACHE_CLEAN);
}

int p1_forward(P1Context *ctx) {
  if(!ctx)return -230;
  hbDNNTaskHandle_t task=NULL;hbDNNTensor *pointer=ctx->outputs;
  hbDNNInferCtrlParam control;HB_DNN_INITIALIZE_INFER_CTRL_PARAM(&control);
  ctx->attempted_forwards++;
  int rc=hbDNNInfer(&task,&pointer,&ctx->input,ctx->handle,&control);
  if(!rc)rc=hbDNNWaitTaskDone(task,0);
  if(!rc&&pointer!=ctx->outputs)rc=-231;
  if(!rc)for(int i=0;i<9;i++){
    rc=hbSysFlushMem(&ctx->outputs[i].sysMem[0],HB_SYS_MEM_CACHE_INVALIDATE);if(rc)break;
  }
  if(task){int released=hbDNNReleaseTask(task);if(!rc)rc=released;}
  if(!rc)ctx->completed_forwards++;
  return rc;
}

void *p1_output_pointer(P1Context *ctx,int index) {
  return (!ctx||index<0||index>=9)?NULL:ctx->outputs[index].sysMem[0].virAddr;
}
uint64_t p1_forward_attempts(P1Context *ctx){return ctx?ctx->attempted_forwards:0;}
uint64_t p1_forward_completions(P1Context *ctx){return ctx?ctx->completed_forwards:0;}
const char *p1_sdk_version(void){return hbDNNGetVersion();}
