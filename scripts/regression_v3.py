#!/usr/bin/env python3
from pathlib import Path
import json,sys,contextlib,io
import fitz
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'));from compose import compose
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True);original=json.loads((R/'assets/editorial/approved.json').read_text())
for a in original['assets']:a['path']=str(R/'assets/editorial'/a['path'])
for m in original['modules']:
 if m.get('image'):m['image']=str(R/'assets/editorial'/m['image'])
def run(name,data):
 source=out/(name+'.json');source.write_text(json.dumps(data,ensure_ascii=False))
 with contextlib.redirect_stdout(io.StringIO()):return compose(source,out/(name+'.pdf'))
def reject(name,edit,expected):
 d=json.loads(json.dumps(original));edit(d)
 try:run(name,d)
 except expected as e:print(name,'PASS',str(e)[:90])
 else:raise AssertionError(name+' was accepted')
reject('long_column',lambda d:d['modules'][2]['columns'][0].update(title='把这一段很长的小标题完整放在左侧窄栏中'),ValueError)
reject('long_budget_label',lambda d:d['modules'][3]['rows'][0].update(label='推荐台与橱窗陈列及阅读空间整体升级'),ValueError)
reject('missing_record',lambda d:d.update(assets=[]),ValueError)
reject('ai_interior',lambda d:d['modules'][2].update(image='cover'),ValueError)
reject('text_collision',lambda d:d['modules'][0].update(title=['甲','乙'],title_size=180),ValueError)
reject('invalid_focus',lambda d:d['modules'][2].update(focus=[1.5,.5]),ValueError)
reject('invalid_range',lambda d:d['modules'][3]['rows'][0].update(low=float('nan')),ValueError)
# Locally drawn geometry is a technical fixture, never presented as a real photo.
im=Image.new('RGB',(2400,1200),'#d9bd83');draw=ImageDraw.Draw(im);draw.ellipse((850,250,1550,950),outline='#17262d',width=12);im.save(out/'aspect-fixture.png')
a={'id':'aspect','path':str(out/'aspect-fixture.png'),'kind':'graphic','subject':'几何裁切测试图，非照片','author':'程序生成','license':'原创测试图'}
d=json.loads(json.dumps(original));d['assets'].append(a);d['include_sources']=True
half={'type':'half','name':'半页图文','kicker':'新增版式 / 图文','title':['一幅图，','留出阅读的空间。'],'image':'otaru','caption':'日本小樽运河 · Haha169 · 2016-02-16','intro':'图像负责场景，\n文字负责解释。','body':'先看空间，再读细节。这一页只演示图片与文字的关系，不把历史照片当作当前现场。'}
pair={'type':'pair','name':'双图并排','title':['两种裁切，','比较观看的方式。'],'images':[{'image':'aspect','caption':'几何测试图 · 左侧焦点','focus':[.2,.5]},{'image':'aspect','caption':'同一几何测试图 · 右侧焦点','focus':[.8,.5]}],'body':'本页两张图是程序绘制的技术测试素材，不是真实场景照片。用来检查保持比例、裁切焦点和图注区域。'}
article={'type':'article','name':'长文与内部目录','columns':1,'blocks':[{'type':'h1','text':'内部导航'},{'type':'toc','items':[{'label':'记录与观察','anchor':'observations'}]},{'type':'break'},{'type':'h1','text':'记录与观察','anchor':'observations'}]+[{'type':'body','text':f'第{i}段。'+('内容增长时保留完整原文，自动续页，并使目录指向真正的全书页码。'*20)} for i in range(9)]}
d['modules'].insert(1,{'type':'contents','name':'目录'});d['modules'][-1:-1]=[half,pair,article]
q=run('all-modules',d);assert q['contents_links'] and not q['missing_text'] and not q['out_of_page_text'];assert len(q['images'])>=4
pdf=fitz.open(out/'all-modules.pdf');starts=q['module_pages'];internal=next(p for p in pdf if '内部导航' in p.get_text());link=next(l for l in internal.get_links() if l['kind']==fitz.LINK_GOTO);assert '记录与观察' in pdf[link['page']].get_text();assert str(link['page']+1) in internal.get_text();print('mixed_modules',len(pdf),'pages, global and internal TOC PASS')
# An available optional asset id must be embedded instead of silently omitted.
opt={'title':'可选图片检查','assets':original['assets'],'modules':[{'type':'article','name':'图文','blocks':[{'type':'body','text':'图片应完整嵌入。'},{'type':'image','path':'otaru','required':False,'caption':'日本小樽运河夜景'}]}]}
oq=run('optional_asset',opt);assert oq['images'] and any(a['id']=='otaru' for a in oq['assets']);print('optional_asset_id PASS')
# Pixel geometry checks: a wide source must be cropped, never stretched, and never upscaled.
from media import Media
m=Media({'assets':[a]},out);p=m.resolve('aspect','half');m.prepare(p,540,720);assert m.images[0]['embedded_pixels']==[900,1200];print('aspect_preserving_crop PASS')
tiny=Image.new('RGB',(60,40));tiny.save(out/'tiny.png')
try:m.prepare(out/'tiny.png',540,720)
except ValueError:print('undersized_image PASS')
else:raise AssertionError('Tiny image accepted')
# An identified subject crossing the binding must warn; this does not replace visual QA.
a['protected_bounds']=[[.4,.3,.6,.7]];mm=Media({'assets':[a]},out);mm.prepare(mm.resolve('aspect','spread'),1080,350,spread=True);assert any('seam' in w for w in mm.warnings);print('protected_subject_seam PASS')
# Contents can continue to multiple pages, with shifted destinations checked.
nav={'title':'目录分页检查','modules':[{'type':'contents','name':'目录'}]+[{'type':'chapter','id':f'c{i}','name':f'章节{i}','title':[f'章节{i}']} for i in range(15)]}
nq=run('multi-contents',nav);assert len(nq['contents_links'])==15 and nq['pages']==17
assert nq['module_pages']['c0']==3 and nq['module_pages']['c14']==17;print('multi_page_contents PASS')
# Preserve the accepted reference before visual review.
run('reproduced',original)
print('ALL CHECKS PASSED')
