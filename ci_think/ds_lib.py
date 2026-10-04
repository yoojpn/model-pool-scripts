import json,urllib.request,time,os
API_KEY=os.environ["OPENROUTER_API_KEY"]
MODEL="deepseek/deepseek-v4-flash-0731"
def call_ds(prompt,max_tokens=3000,reasoning_off=True,temperature=0.3):
    body={"model":MODEL,"messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens,"temperature":temperature,
          "provider":{"only":["DeepInfra"],"allow_fallbacks":False,"data_collection":"deny"}}
    if reasoning_off: body["reasoning"]={"enabled":False}
    last=None
    for a in range(3):
        try:
            req=urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",data=json.dumps(body).encode(),headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"})
            d=json.loads(urllib.request.urlopen(req,timeout=120).read())
            ch=d["choices"][0]
            return ch["message"].get("content") or "",d.get("usage",{}),{"provider":d.get("provider"),"finish":ch.get("finish_reason"),"model":d.get("model"),"reasoning_len":len(ch["message"].get("reasoning") or "")}
        except urllib.error.HTTPError as e:
            last=f"HTTP {e.code}: {e.read()[:300]}"; time.sleep(2)
        except Exception as e:
            last=str(e); time.sleep(2)
    return "",{"error":last},{}
