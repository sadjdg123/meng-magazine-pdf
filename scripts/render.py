#!/usr/bin/env python3
"""Deterministic Chinese editorial PDF renderer. Only local, explicitly supplied content."""
import argparse, html, json, re, unicodedata, hashlib, io
from functools import partial
from collections import Counter
from reportlab.lib import textsplit
from reportlab.platypus import paragraph as rlparagraph
# Extend Japanese defaults with Chinese punctuation.
textsplit.ALL_CANNOT_START += "，。；：！？、）》」』】％”’"
rlparagraph.ALL_CANNOT_START = textsplit.ALL_CANNOT_START
from reportlab.pdfgen.canvas import Canvas
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, LongTable, TableStyle, Flowable, KeepTogether
from fontTools.ttLib import TTFont as Font
import fitz
from PIL import Image, ImageOps
ROOT=Path(__file__).resolve().parents[1]

def clean(text):
    # Normalize compatibility ideographs only; preserve editorial punctuation.
    return ''.join(unicodedata.normalize('NFKC',c) if 0xF900<=ord(c)<=0xFAFF or 0x2F800<=ord(c)<=0x2FA1F else c for c in str(text))
def norm(text):return re.sub(r'\s+','',clean(text))

def setup_fonts(cache,tokens):
    maps={}
    for role,file in tokens['fonts'].items():
        src=ROOT/'assets/fonts'/file
        fingerprint=hashlib.sha256(src.read_bytes()).hexdigest()[:12]
        target=cache/(fingerprint+'.ttf')
        font=Font(src)
        maps[role]=font.getBestCmap()
        if not target.exists():
            font.flavor=None
            for record in font['name'].names:
                if record.nameID in (1,3,4,6):
                    value='MengEditorial'+role.title()
                    record.string=value.encode(record.getEncoding(),errors='replace')
            font.save(target)
        pdfmetrics.registerFont(TTFont(role,str(target)))
    return maps

class Picture(Flowable):
    def __init__(self,path,width,height,focus=(.5,.5),media_context=None):
        Flowable.__init__(self);self.width=width;self.height=height
        from media import Media
        self.image=(media_context or Media({},Path(path).parent)).prepare(path,width,height,focus)
    def draw(self):self.canv.drawImage(self.image,0,0,self.width,self.height)

class Rule(Flowable):
    def __init__(self,width,color):Flowable.__init__(self);self.width=width;self.height=9;self.color=color
    def draw(self):self.canv.setStrokeColor(self.color);self.canv.setLineWidth(.5);self.canv.line(0,4,self.width,4)

class Doc(BaseDocTemplate):
    def afterFlowable(self,flowable):
        if getattr(flowable,'anchor',None):
            key=flowable.anchor;self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(),key,0)
            self.sections[key]=self.page

def render(input_path, output_path,media_context=None):
    input_path=Path(input_path).resolve();output_path=Path(output_path).resolve();output_path.parent.mkdir(parents=True,exist_ok=True)
    cache=output_path.parent/'.font-cache';cache.mkdir(exist_ok=True)
    data=json.loads(input_path.read_text());tokens=json.loads((ROOT/'assets/style.json').read_text())
    maps=setup_fonts(cache,tokens);p=tokens['page'];W,H=p['width'],p['height'];M=p['margin']
    column_count=int(data.get('columns',1))
    if column_count not in (1,2):raise ValueError('columns must be 1 or 2')
    if column_count==2 and any(b['type']=='table' for b in data['blocks']):raise ValueError('Place tables in a separate one-column article module')
    gap=p.get('column_gap',18);CW=(W-2*M-gap)/2 if column_count==2 else W-2*M
    page_offset=int(data.get('page_offset',0))
    if page_offset<0:raise ValueError('page_offset must be non-negative')
    colors={k:HexColor(v) for k,v in tokens['colors'].items()}
    styles={}
    for name,(size,lead) in tokens['type'].items():
        role='title' if name in ('title','h1') else ('serif' if name=='intro' else ('label' if name in ('h2','label') else 'body'))
        styles[name]=ParagraphStyle(name,fontName=role,fontSize=size,leading=lead,textColor=colors['ink'],wordWrap='CJK',spaceAfter=8,allowWidows=0,allowOrphans=0,keepWithNext=name in ('h1','h2','label'))
    styles['small'].textColor=colors['muted']
    styles['label'].textColor=colors['ink']
    styles['kicker']=ParagraphStyle('kicker',parent=styles['label'],textColor=colors['accent'])
    expected=[];warnings=[]
    def para(text,kind='body',link=None,anchor=None):
        text=clean(text);role=styles[kind].fontName
        missing=sorted(set(c for c in text if not c.isspace() and ord(c) not in maps[role]))
        if missing:raise ValueError(f'Missing glyphs in {role}: {missing}')
        expected.append(text)
        markup=html.escape(text).replace('\n','<br/>')
        if link:
            if not re.match(r'^(https?://|#)',link):raise ValueError('Only http(s) and internal links supported')
            markup=f'<link href="{html.escape(link,quote=True)}">{markup}</link>'
        obj=Paragraph(markup,styles[kind]);obj.anchor=anchor
        return obj
    def image_block(block):
        path=(input_path.parent/block['path']).resolve()
        if not path.exists():
            if block.get('required',True):raise FileNotFoundError(path)
            warnings.append(f"Optional image omitted: {block['path']}");return []
        result=[Picture(path,CW,block.get('height',180),block.get('focus',[.5,.5]),media_context),Spacer(1,6)]
        if block.get('caption'):result.append(para(block['caption'],'small'))
        return result
    def table(block):
        rows=block['rows'];n=len(rows[0]);weights=block.get('widths',[1]*n)
        if len(weights)!=n or any(len(row)!=n for row in rows):raise ValueError('Table dimensions do not agree')
        cells=[[para(str(v),'small' if i else 'label') for v in row] for i,row in enumerate(rows)]
        t=LongTable(cells,colWidths=[CW*w/sum(weights) for w in weights],repeatRows=1,splitByRow=1,splitInRow=1,hAlign='LEFT')
        t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'body'),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),('LINEBELOW',(0,0),(-1,0),.7,colors['ink']),('LINEBELOW',(0,1),(-1,-1),.35,colors['rule'])]))
        return t
    doc=Doc(str(output_path),pagesize=(W,H),leftMargin=M,rightMargin=M,topMargin=p['top'],bottomMargin=p['bottom'],title=clean(data['title']),author=data.get('author','门哥'),pageCompression=1,initialFontName='body')
    doc.sections={}
    # Two builds provide real page numbers in contents and a stable total folio.
    pages={};total=0
    def page(canvas,document):
        canvas.saveState();canvas.setFillColor(colors['paper']);canvas.rect(0,0,W,H,fill=1,stroke=0)
        if document.page>1:
            canvas.setFillColor(colors['muted']);canvas.setFont('body',9)
            canvas.drawString(M,H-28,clean(data.get('running_title','专属文集')))
            canvas.drawRightString(W-M,H-28,clean(data.get('edition','01')))
        canvas.setStrokeColor(colors['rule']);canvas.setLineWidth(.4);canvas.line(M,31,W-M,31)
        canvas.setFillColor(colors['muted']);canvas.setFont('body',9)
        canvas.drawString(M,18,clean(data.get('footer','')))
        canvas.drawRightString(W-M,18,f'{document.page+page_offset:02d}'+(f' / {total:02d}' if total and not data.get('global_numbering') else ''))
        canvas.restoreState()
    doc.addPageTemplates([PageTemplate(id='main',frames=[Frame(M+i*(CW+gap),p['bottom'],CW,H-p['top']-p['bottom'],leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0) for i in range(column_count)],onPage=page)])
    def story():
        out=[]
        for block in data['blocks']:
            kind=block['type']
            if kind=='break':out.append(PageBreak())
            elif kind=='space':out.append(Spacer(1,block.get('height',10)))
            elif kind=='rule':out.append(Rule(CW,colors['rule']))
            elif kind=='image':out.extend(image_block(block))
            elif kind=='table':out.append(table(block));out.append(Spacer(1,12))
            elif kind=='toc':
                for item in block['items']:
                    t=LongTable([[para(item['label'],'intro',link='#'+item['anchor']),para(str(pages[item['anchor']]+page_offset) if item['anchor'] in pages else '—','intro')]],colWidths=[CW-35,35])
                    t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'body'),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),('LINEBELOW',(0,0),(-1,-1),.35,colors['rule'])]));out.append(t)
            elif kind=='day':
                # Keep a heading and one paragraph together; long paragraphs may split.
                out.append(para(block['label']+'  '+block['title'],'h2'));out.append(para(block['text']));out.append(Spacer(1,4))
            elif kind=='quote':
                out.append(Spacer(1,16));out.append(para(block['text'],'h1'));out.append(Spacer(1,16))
            elif kind in styles:out.append(para(block['text'],kind,block.get('link'),block.get('anchor')))
            else:raise ValueError(f'Unknown block type: {kind}')
        return out
    # Preflight metadata too.
    for key in ('title','author','running_title','edition','footer'):
        for char in clean(data.get(key,'')):
            if not char.isspace() and ord(char) not in maps['body']:raise ValueError(f'Metadata missing glyph: {char}')
    folio_width=44
    if pdfmetrics.stringWidth(clean(data.get('footer','')),'body',9)>W-2*M-folio_width-12:raise ValueError('Footer exceeds reserved label region')
    header_width=pdfmetrics.stringWidth(clean(data.get('running_title','专属文集')),'body',9)
    edition_width=pdfmetrics.stringWidth(clean(data.get('edition','01')),'body',9)
    if header_width+edition_width+18>W-2*M:raise ValueError('Header labels overlap')
    doc.build(story(),canvasmaker=partial(Canvas,initialFontName='body'));pages=dict(doc.sections)
    first=fitz.open(output_path);total=len(first);first.close();expected.clear();warnings.clear()
    doc.sections={};doc.build(story(),canvasmaker=partial(Canvas,initialFontName='body'))
    pdf=fitz.open(output_path)
    extracted=''.join(page.get_text(clip=fitz.Rect(0,p['top']-5,W,H-p['bottom']+6)) for page in pdf)
    flat=norm(extracted)
    without_repeats=flat
    for b in data['blocks']:
        if b['type']=='table':
            header=norm(''.join(map(str,b['rows'][0])))
            without_repeats=without_repeats.replace(header,'')
    counts=Counter(norm(s) for s in expected if norm(s))
    missing=[s for s,n in counts.items() if max(flat.count(s),without_repeats.count(s))<n]
    # Text elements are checked against the page and reserved footer region.
    bounds=[]
    for index,page in enumerate(pdf):
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                x0,y0,x1,y1=line['bbox']
                if x0<0 or y0<0 or x1>W+.2 or y1>H+.2:bounds.append({'page':index+1,'bbox':line['bbox']})
    fonts=[]
    for xref in sorted({f[0] for pg in pdf for f in pg.get_fonts()}):
        base,ext,typ,content=pdf.extract_font(xref);fonts.append({'name':base,'embedded':bool(content)})
    report={'input':str(input_path),'output':str(output_path),'pages':len(pdf),'size_bytes':output_path.stat().st_size,'sections':doc.sections,'expected_text_blocks':len(expected),'missing_text':missing,'out_of_page_text':bounds,'fonts':fonts,'warnings':warnings,'page_count_stable':len(pdf)==total,'toc_stable':pages==doc.sections}
    pdf.close();output_path.with_suffix('.qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if missing or bounds or not all(f['embedded'] for f in fonts) or not report['page_count_stable'] or not report['toc_stable']:raise ValueError('PDF validation failed; see .qa.json')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('output');args=parser.parse_args();render(args.input,args.output)
