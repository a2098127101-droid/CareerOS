(function(global){
  'use strict';
  class StepInLearnerAgentClient {
    constructor(options={}){
      this.baseUrl=String(options.baseUrl||'').replace(/\/$/,'');
      this.api=this.baseUrl+'/api/learner-agent/v1';
      this.credentials=options.credentials||'same-origin';
      this.headers={...(options.headers||{})};
    }
    async request(path,options={}){
      const headers={...this.headers,...(options.headers||{})};
      if(options.body!==undefined&&!headers['Content-Type'])headers['Content-Type']='application/json';
      const response=await fetch(this.api+path,{credentials:this.credentials,...options,headers});
      const data=await response.json().catch(()=>({}));
      if(!response.ok){
        const detail=data&&data.detail;
        const message=(detail&&detail.message)||detail||('Learner Agent request failed: '+response.status);
        const error=new Error(typeof message==='string'?message:JSON.stringify(message));
        error.status=response.status;error.payload=data;throw error;
      }
      return data;
    }
    manifest(){return this.request('/manifest');}
    tools(){return this.request('/tools');}
    state(params=''){return this.request('/state'+(params?('?'+params):''));}
    memory(params=''){return this.request('/memory'+(params?('?'+params):''));}
    decisions(params=''){return this.request('/decisions'+(params?('?'+params):''));}
    observe(observation){return this.request('/observe',{method:'POST',body:JSON.stringify(observation||{})});}
    step(input){return this.request('/step',{method:'POST',body:JSON.stringify(input||{})});}
    evaluate(input){return this.request('/evaluate',{method:'POST',body:JSON.stringify(input||{})});}
  }
  global.StepInLearnerAgentClient=StepInLearnerAgentClient;
  global.StepInLearnerAgent=global.StepInLearnerAgent||new StepInLearnerAgentClient();
})(window);
