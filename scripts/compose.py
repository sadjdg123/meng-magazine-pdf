from pathlib import Path
import json,io,html,re,unicodedata,sys
from PIL import Image,ImageOps
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor,Color
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib import textsplit
from reportlab.platypus import paragraph as rlparagraph
from fontTools.ttLib import TTFont as Font
import fitz

import argparse,math,tempfile
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
LAYOUTS=json.loads((ROOT/'assets/layouts.json').read_text())
media=None
TOKENS=json.loads((ROOT/'assets/style.json').read_text())
W,H=TOKENS['page']['width'],TOKENS['page']['height']
if (W,H)!=(540,720):raise ValueError('Editorial module grid requires 540 x 720 pt')
PAPER=TOKENS['colors']['paper'];INK=TOKENS['colors']['ink'];RED=TOKENS['colors']['accent'];GOLD=TOKENS['colors']['gold'];GREY=TOKENS['colors']['muted']
textsplit.ALL_CANNOT_START+='，。；：！？、）》」』】％”’';rlparagraph.ALL_CANNOT_START=textsplit.ALL_CANNOT_START
c=None;cmap={};expected=[];boxes=[]
def load_fonts(cache):
 for name,key in [('Display','title'),('Serif','serif'),('Body','body'),('Label','label')]:
  file=json.loads((ROOT/'assets/style.json').read_text())['fonts'][key]
  f=Font(ROOT/'assets/fonts'/file);cmap[name]=f.getBestCmap();f.flavor=None
  for record in f['name'].names:
   if record.nameID in (1,3,4,6):record.string=('EditorialModule'+name).encode(record.getEncoding(),errors='replace')
  path=cache/(name+'.ttf');f.save(path);pdfmetrics.registerFont(TTFont(name,str(path)))
def clean(text):
 return "".join(unicodedata.normalize("NFKC",ch) if 0xF900<=ord(ch)<=0xFAFF or 0x2F800<=ord(ch)<=0x2FA1F else ch for ch in str(text))
def check(text,font):
 for char in text:
  if not char.isspace() and ord(char) not in cmap[font]:raise ValueError(f'缺字: {font} {char}')
def bg(color):c.setFillColor(HexColor(color));c.rect(0,0,W,H,stroke=0,fill=1)
def rect(x,y,w,h,color):c.setFillColor(HexColor(color));c.rect(x,H-y-h,w,h,fill=1,stroke=0)
def line(x,y,x2,y2,color=INK,width=.5):c.setStrokeColor(HexColor(color));c.setLineWidth(width);c.line(x,H-y,x2,H-y2)
def text(s,x,y,size=11,font='Body',color=INK,align='left',max_width=None):
 s=clean(s);check(s,font);c.setFillColor(HexColor(color));c.setFont(font,size)
 width=pdfmetrics.stringWidth(s,font,size)
 if max_width is not None and width>max_width+.1:raise ValueError('Text exceeds its column width; edit this heading/label or move full content to article: '+s[:35])
 xx=x if align=='left' else x-width
 if xx<-.1 or xx+width>W+.1 or y<0 or y+size>H:raise ValueError(f'文字越界: {s}')
 c.drawString(xx,H-y-size,s);expected.append(s)
 if s.strip():boxes.append((c.getPageNumber(),xx,y,xx+width,y+size,s))
def para(s,x,y,width,size=11.5,leading=19,font='Body',color=INK,max_height=None):
 s=clean(s);check(s,font)
 sty=ParagraphStyle('p',fontName=font,fontSize=size,leading=leading,textColor=HexColor(color),wordWrap='CJK',allowWidows=0,allowOrphans=0)
 p=Paragraph(html.escape(s).replace('\n','<br/>'),sty);_,h=p.wrap(width,H)
 if y+h>H-28 or (max_height is not None and h>max_height):raise ValueError('Text exceeds module capacity. Move full text to an article continuation; do not delete it: '+s[:30])
 p.drawOn(c,x,H-y-h);expected.append(s)
 if s.strip():boxes.append((c.getPageNumber(),x,y,x+width,y+h,s))
 return h

def photo(path,x,y,width,height,focus=(.5,.5),source_box=None):
 fullwidth,fullheight,offset=source_box or (width,height,0)
 image=media.prepare(path,fullwidth,fullheight,focus,spread=bool(source_box))
 c.saveState();clip=c.beginPath();clip.rect(x,H-y-height,width,height);c.clipPath(clip,stroke=0,fill=0)
 c.drawImage(image,x-offset,H-y-fullheight,fullwidth,fullheight);c.restoreState()
def footer(n,color=GREY,section=None):
 emit(section or '',LAYOUTS['footer']['label'],color)
 emit(f'{n:02d}',LAYOUTS['footer']['number'],color)
def bookmark(key,label):c.bookmarkPage(key);c.addOutlineEntry(label,key,0)
def curve(points,color,width):
 c.setStrokeColor(HexColor(color));c.setLineWidth(width);c.setLineCap(0)
 p=c.beginPath();p.moveTo(points[0][0],H-points[0][1])
 for a,b,d in points[1:]:p.curveTo(a[0],H-a[1],b[0],H-b[1],d[0],H-d[1])
 c.drawPath(p,stroke=1,fill=0)


def headline(lines,x,y,size,leading,font='Display',color=INK,min_size=38,max_width=468):
 if isinstance(lines,str):lines=lines.split('\n')
 if not 1<=len(lines)<=2:raise ValueError('Headlines require one or two intentional lines; retain longer text in article')
 lines=[clean(s) for s in lines]
 natural=max(pdfmetrics.stringWidth(s,font,size) for s in lines)
 fitted=min(size,size*max_width/max(natural,1))
 if fitted<min_size:raise ValueError('Headline is too long; split into two lines or use an article heading')
 for i,s in enumerate(lines):text(s,x,y+i*leading,fitted,font,color)

def emit(value,spec,color=INK):
 args=dict(spec)
 if 'leading' not in args:text(value,color=color,**args)
 elif 'width' in args:para(value,color=color,**args)
 else:headline(value,color=color,**args)
def collisions():
 errors=[]
 for i,a in enumerate(boxes):
  for b in boxes[i+1:]:
   if a[0]==b[0] and min(a[3],b[3])-max(a[1],b[1])>.5 and min(a[4],b[4])-max(a[2],b[2])>.5:errors.append([a[5],b[5]])
 if errors:raise ValueError('Text regions overlap: '+str(errors))
 return errors

def draw_module(m,page_num,input_dir):
 kind=m['type'];cfg=LAYOUTS[kind];links=[]
 def field(key,color=INK,value=None,changes=None):
  spec=dict(cfg[key]);spec.update(changes or {});emit(m.get(key,'') if value is None else value,spec,color)
 def image(value,window,focus=(.5,.5),spread=None):
  path=media.resolve(value,kind);photo(path,*window,focus=focus,source_box=spread)
 def motif():
  if 'sun' in cfg:
   x,y,r=cfg['sun'];c.setFillColor(HexColor(GOLD));c.circle(x,H-y,r,fill=1,stroke=0)
  if 'curve' in cfg:curve(cfg['curve'],RED,cfg['curve_width'])
 bg(INK if kind=='back' else PAPER)
 if kind=='cover':
  if m.get('image'):image(m['image'],cfg['image'],m.get('focus',[.5,.5]))
  else:
   motif();field('summary')
  field('brand');field('edition');field('title',changes={'size':m.get('title_size',cfg['title']['size'])})
  count=len(m['title'].split('\n') if isinstance(m['title'],str) else m['title'])
  field('subtitle',changes={'y':cfg['subtitle']['y'] if count==1 else cfg['subtitle_two_y']})
  rect(0,cfg['footer_band_y'],W,H-cfg['footer_band_y'],PAPER);field('footer');c.showPage()
 elif kind=='chapter':
  background=INK if m.get('theme','red')=='dark' else RED;bg(background)
  curve(cfg['curve1'],GOLD,cfg['curve_widths'][0]);curve(cfg['curve2'],INK if background==RED else RED,cfg['curve_widths'][1])
  for key in ('kicker','number','title','intro','secondary_title','body','list_title','list_text'):field(key,PAPER)
  line(*cfg['rule'],PAPER,.8);footer(page_num,PAPER,m.get('footer'));c.showPage()
 elif kind=='spread':
  cols=m['columns'];steps=m.get('steps',[])
  if len(cols)!=2 or len(steps)>3:raise ValueError('Spread requires two text columns and 0-3 summary steps')
  window=cfg['image']
  for side in (0,1):
   bg(PAPER);image(m['image'],window,m.get('focus',[.5,.5]),(window[2]*2,window[3],side*window[2]))
   if side==0:
    field('kicker',RED);field('title');field('intro');footer(page_num,section=m.get('footer'))
   else:
    field('right_title')
    for col,x in zip(cols,cfg['column_x']):
     field('column_title',value=col['title'],changes={'x':x});field('column_body',value=col['text'],changes={'x':x})
    line(*cfg['rule'],INK,.5)
    for i,(step,x) in enumerate(zip(steps,cfg['step_x'])):
     available=(cfg['step_x'][i+1]-x-18) if i+1<len(cfg['step_x']) else W-TOKENS['page']['margin']-x
     field('step_title',value=step['title'],changes={'x':x,'max_width':available})
     field('step_label',value=step.get('label',''),changes={'x':x,'max_width':available})
    footer(page_num+1,section=m.get('caption'))
   c.showPage()
 elif kind=='budget':
  rows=m['rows']
  if not 1<=len(rows)<=5:raise ValueError('Range module supports 1-5 rows')
  for row in rows:
   if not all(isinstance(row[k],(int,float)) and not isinstance(row[k],bool) and math.isfinite(row[k]) for k in ('low','high')) or not 0<=row['low']<=row['high']:raise ValueError('Range must satisfy finite 0 <= low <= high')
  maxv=m.get('axis_max')
  if maxv is None:
   highest=max(row['high'] for row in rows);power=10**math.floor(math.log10(highest or 1));maxv=next(x*power for x in (1,2,5,10) if x*power>=highest)
  if not isinstance(maxv,(int,float)) or not math.isfinite(maxv) or maxv<=0 or maxv<max(row['high'] for row in rows):raise ValueError('Axis does not contain values')
  for key in ('kicker','unit','title','intro'):field(key)
  left,right,top,bottom,label_y=cfg['axis']
  for v in (0,maxv/2,maxv):
   x=left+(right-left)*v/maxv;line(x,top,x,bottom,TOKENS['colors']['rule'],.5)
   axis_spec=dict(cfg['axis_label']);dx=axis_spec.pop('x_offset');text(f'{v/10000:g}万' if v>=10000 else f'{v:g}',x+dx,label_y,color=GREY,**axis_spec)
  for i,row in enumerate(rows):
   y=cfg['row'][0]+i*cfg['row'][1];field('label',value=row['label'],changes={'y':y-8})
   lo,hi=row['low'],row['high'];a=left+(right-left)*lo/maxv;b=left+(right-left)*hi/maxv;line(a,y,b,y,RED,cfg['range_width'])
   c.setFillColor(HexColor(INK));c.circle(a,H-y,cfg['marker_radius'],fill=1,stroke=0);c.setFillColor(HexColor(RED));c.circle(b,H-y,cfg['marker_radius'],fill=1,stroke=0)
   field('value',value=f'{lo:,} - {hi:,}',changes={'y':y-7})
  line(*cfg['rule'],INK,.6);field('note_title');field('note');footer(page_num,section=m.get('footer'));c.showPage()
 elif kind=='back':
  motif()
  for key in ('brand','edition','title','intro','byline','edition_note','credits','footer'):field(key,PAPER)
  line(*cfg['rule'],PAPER,.6)
  if m.get('source_url'):
   if not m['source_url'].startswith(('https://','http://')):raise ValueError('Source URL must use http(s)')
   field('source_label',PAPER,value=m.get('source_label','资料来源'));spec=cfg['source_label'];c.linkURL(m['source_url'],(spec['x'],H-spec['y']-14,spec['x']+spec['max_width'],H-spec['y']),relative=0,thickness=0)
  c.showPage()
 elif kind=='half':
  field('kicker',RED);field('title');image(m['image'],cfg['image'],m.get('focus',[.5,.5]));field('caption',GREY);field('intro');field('body');footer(page_num,section=m.get('footer'));c.showPage()
 elif kind=='pair':
  if len(m['images'])!=2:raise ValueError('Pair requires exactly two real images')
  field('kicker',RED);field('title')
  for im,x in zip(m['images'],cfg['image_x']):
   image(im['image'],[x,cfg['image_y'],cfg['image_width'],cfg['image_height']],im.get('focus',[.5,.5]));field('caption',GREY,value=im.get('caption',''),changes={'x':x})
  field('body');footer(page_num,section=m.get('footer'));c.showPage()
 elif kind=='contents':
  entries=m['_entries'];per_page=int((cfg['bottom']-cfg['entry_y'])//cfg['row_height'])
  for j in range(max(1,math.ceil(len(entries)/per_page))):
   bg(PAPER);field('kicker',RED,value=m.get('kicker','全书导航'));field('title',value=m.get('title',['目录。']))
   for k,item in enumerate(entries[j*per_page:(j+1)*per_page]):
    y=cfg['entry_y']+k*cfg['row_height'];field('label',value=item['label'],changes={'y':y});field('number',value=f"{item['page']:02d}",changes={'y':y})
    line(36,y+28,504,y+28,TOKENS['colors']['rule'],cfg['rule_width']);links.append({'local_page':j,'target':item['page']-1,'rect':[36,y,504,y+28]})
   footer(page_num+j,section=m.get('footer'));c.showPage()
 else:raise ValueError('Unknown module: '+kind)
 return links

def inspect_pdf(path,expected_strings):
 pdf=fitz.open(path);flat=re.sub(r'\s+','',''.join(p.get_text() for p in pdf));counts=Counter(re.sub(r'\s+','',s) for s in expected_strings if s.strip())
 missing=[s for s,n in counts.items() if flat.count(s)<n];overflow=[]
 for i,page in enumerate(pdf):
  for block in page.get_text('dict')['blocks']:
   for ln in block.get('lines',[]):
    x0,y0,x1,y1=ln['bbox']
    if min(x0,y0)<-.5 or x1>W+.5 or y1>H+.5:overflow.append((i+1,ln['bbox']))
 fonts=[]
 for x in sorted({f[0] for page in pdf for f in page.get_fonts()}):
  name,ext,typ,content=pdf.extract_font(x);fonts.append({'name':name,'embedded':bool(content)})
 report={'pages':len(pdf),'text_blocks':len(expected_strings),'missing_text':missing,'out_of_page_text':overflow,'fonts':fonts};pdf.close()
 if missing or overflow or not all(f['embedded'] for f in fonts):raise ValueError(report)
 return report

def compose(input_file,output_file):
 global c,expected,boxes,media,TOKENS,LAYOUTS,W,H,PAPER,INK,RED,GOLD,GREY
 from media import Media
 from render import render
 input_file=Path(input_file).resolve();output_file=Path(output_file).resolve();output_file.parent.mkdir(parents=True,exist_ok=True)
 TOKENS=json.loads((ROOT/'assets/style.json').read_text());LAYOUTS=json.loads((ROOT/'assets/layouts.json').read_text())
 W,H=TOKENS['page']['width'],TOKENS['page']['height']
 if (W,H)!=(540,720):raise ValueError('Editorial grid requires 540 x 720 pt')
 PAPER,INK,RED,GOLD,GREY=[TOKENS['colors'][k] for k in ('paper','ink','accent','gold','muted')]
 data=json.loads(input_file.read_text());modules=data.get('modules')
 if not modules:raise ValueError('Provide modules')
 modules=json.loads(json.dumps(modules));media=Media(data,input_file.parent)
 # Asset records are mandatory for every embedded image, before any PDF is written.
 usage={}
 for m in modules:
  candidates=([m['image']] if m.get('image') else [])+[im['image'] for im in m.get('images',[])]+[b['path'] for b in m.get('blocks',[]) if b['type']=='image']
  for value in candidates:
   if value in usage and not m.get('repeat_reason'):media.warnings.append('Repeated asset across modules; check editorial necessity: '+str(value))
   usage[value]=m['type']
  if m.get('image'):media.resolve(m['image'],m['type'])
  for im in m.get('images',[]):media.resolve(im['image'],m['type'])
  for block in m.get('blocks',[]):
   if block['type']=='image':
    if block['path'] in media.records or block.get('required',True) or (input_file.parent/block['path']).is_file():block['path']=str(media.resolve(block['path'],'article'))
 if media.used and data.get('include_sources',True):
  source={'type':'article','id':'asset-sources','name':'图片来源与许可','columns':1,'running_title':data.get('brand',''),'footer':'素材来源 / 记录','blocks':media.sources_blocks()}
  back=next((i for i,m in enumerate(modules) if m['type']=='back'),len(modules));modules.insert(back,source)
 for i,m in enumerate(modules):m.setdefault('id',f'module-{i+1}')
 if len({m['id'] for m in modules})!=len(modules):raise ValueError('Module ids must be unique')
 index_entries=[m for m in modules if m['type'] not in ('contents','cover','back') and m.get('in_contents',True)]
 per_page=int((LAYOUTS['contents']['bottom']-LAYOUTS['contents']['entry_y'])//LAYOUTS['contents']['row_height'])
 with tempfile.TemporaryDirectory(prefix='editorial-',dir=output_file.parent) as work:
  work=Path(work);load_fonts(work);parts=[];all_expected=[];start=1
  for i,m in enumerate(modules):
   part=work/f'part-{i}.pdf';links=[]
   if m['type']=='contents':
    count=max(1,math.ceil(len(index_entries)/per_page));report=None
   elif m['type']=='article':
    article={'title':data['title'],'author':data.get('author','门哥'),'running_title':m.get('running_title',data.get('brand','')),'edition':data.get('edition',''),'footer':m.get('footer',''),'blocks':m['blocks'],'columns':m.get('columns',1),'page_offset':start-1,'global_numbering':True}
    source=work/f'article-{i}.json';source.write_text(json.dumps(article,ensure_ascii=False));report=render(source,part,media_context=media);count=report['pages']
    original=fitz.open(part)
    refs={pg.xref:j for j,pg in enumerate(original)}
    for j,pg in enumerate(original):
     for l in pg.get_links():
      if l['kind'] in (fitz.LINK_GOTO,fitz.LINK_NAMED):
       if l['kind']==fitz.LINK_GOTO:target=l['page']
       else:
        raw=original.xref_object(l['xref']);match=re.search(r'/Dest\s*\[\s*(\d+)\s+0\s+R',raw)
        if not match or int(match[1]) not in refs:raise ValueError('Unresolved article navigation link')
        target=refs[int(match[1])]
       links.append({'local_page':j,'target':start-1+target,'rect':list(l['from'])})
      elif l['kind']==fitz.LINK_URI:links.append({'local_page':j,'uri':l['uri'],'rect':list(l['from'])})
      else:raise ValueError('Unsupported article link kind')
    all_expected.extend(''.join(s['text'] for s in ln['spans']) for pg in original for b in pg.get_text('dict')['blocks'] for ln in b.get('lines',[]) if ln['bbox'][1]<H-TOKENS['page']['bottom']);original.close()
   else:
    expected=[];boxes=[];c=canvas.Canvas(str(part),pagesize=(W,H),pageCompression=1,initialFontName='Body');c.setTitle(data['title']);c.setAuthor(data.get('author','门哥'))
    draw_module(m,start,input_file.parent);collisions();c.save()
    check_links=fitz.open(part)
    for j,pg in enumerate(check_links):
     for l in pg.get_links():
      if l['kind']==fitz.LINK_URI:links.append({'local_page':j,'uri':l['uri'],'rect':list(l['from'])})
    check_links.close();report=inspect_pdf(part,expected);report['text_collisions']=[];all_expected.extend(expected);count=report['pages']
   parts.append({'module':m,'path':part,'start':start,'count':count,'report':report,'links':links});start+=count
  starts={p['module']['id']:p['start'] for p in parts}
  for p in parts:
   if p['module']['type']=='contents':
    m=p['module'];m['_entries']=[{'label':q.get('name',q['type']),'page':starts[q['id']]} for q in index_entries]
    expected=[];boxes=[];c=canvas.Canvas(str(p['path']),pagesize=(W,H),pageCompression=1,initialFontName='Body');p['links']=draw_module(m,p['start'],input_file.parent);collisions();c.save();p['report']=inspect_pdf(p['path'],expected);all_expected.extend(expected)
    if p['report']['pages']!=p['count']:raise ValueError('Contents pagination mismatch')
  joined=fitz.open();toc=[]
  for p in parts:
   src=fitz.open(p['path']);joined.insert_pdf(src,links=False);src.close();toc.append([1,p['module'].get('name',p['module']['type']),p['start']])
  for p in parts:
   for link in p['links']:
    dest={'kind':fitz.LINK_URI,'uri':link['uri']} if 'uri' in link else {'kind':fitz.LINK_GOTO,'page':link['target'],'to':fitz.Point(0,0)}
    dest['from']=fitz.Rect(link['rect']);joined[p['start']-1+link['local_page']].insert_link(dest)
  joined.set_toc(toc);joined.set_metadata({'title':data['title'],'author':data.get('author','门哥'),'creator':'Meng Magazine PDF v3'});joined.subset_fonts();joined.save(output_file,garbage=4,deflate=True);joined.close()
  final=inspect_pdf(output_file,all_expected)
  doc=fitz.open(output_file);verified=[]
  for p in parts:
   for l in p['links']:
    page=doc[p['start']-1+l['local_page']]
    if 'uri' in l:
     if not any(x.get('uri')==l['uri'] for x in page.get_links()):raise ValueError('Source link validation failed')
     continue
    matches=[x for x in page.get_links() if x.get('kind')==fitz.LINK_GOTO and x.get('page')==l['target'] and fitz.Rect(x['from']).intersects(fitz.Rect(l['rect']))]
    if not matches:raise ValueError('Contents link validation failed')
    verified.append({'page':p['start']+l['local_page'],'target_page':l['target']+1})
  doc.close();final.update({'version':'3.0','output':str(output_file),'modules':[p['report'] for p in parts],'module_pages':starts,'contents_links':verified,'images':media.images,'assets':list(media.used.values()),'warnings':media.warnings,'size_bytes':output_file.stat().st_size,'paper':PAPER})
  output_file.with_suffix('.qa.json').write_text(json.dumps(final,ensure_ascii=False,indent=2));print(json.dumps(final,ensure_ascii=False,indent=2));return final

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('output');args=parser.parse_args();compose(args.input,args.output)
