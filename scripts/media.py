"""Real-asset records and aspect-preserving, size-aware raster preparation."""
from pathlib import Path
import hashlib,io,json
from PIL import Image,ImageOps
from reportlab.lib.utils import ImageReader
ROOT=Path(__file__).resolve().parents[1]
class Media:
 def __init__(self,data,input_dir):
  self.base=Path(input_dir);self.records={};self.by_path={};self.used={};self.warnings=[];self.prepared={};self.images=[]
  self.config=json.loads((ROOT/'assets/style.json').read_text())['images']
  for a in data.get('assets',[]):
   if a.get('id') in self.records:raise ValueError('Duplicate asset id')
   for key in ('id','path','kind','subject','author','license'):
    if not a.get(key):raise ValueError('Asset record requires '+key)
   if a['kind'] not in ('photo','user_photo','ai_cover','graphic'):raise ValueError('Unknown asset kind')
   if a['kind']=='photo' and not str(a.get('source_url','')).startswith(('https://','http://')):raise ValueError('Web photo requires original source_url')
   for key in ('source_url','license_url'):
    if a.get(key) and not a[key].startswith(('https://','http://')):raise ValueError('Asset URL must use http(s)')
   path=(self.base/a['path']).resolve();self.records[a['id']]=a;self.by_path[str(path)]=a
 def resolve(self,value,usage):
  a=self.records.get(value) or self.by_path.get(str((self.base/value).resolve()))
  if not a:raise ValueError('Every embedded image requires an assets record: '+str(value))
  if a['kind']=='ai_cover' and usage!='cover':raise ValueError('AI cover assets are forbidden in interior pages')
  path=(self.base/a['path']).resolve()
  if not path.is_file():raise FileNotFoundError(path)
  if a['id'] not in self.used:self.used[a['id']]=a
  return path
 def prepare(self,path,width,height,focus=(.5,.5),spread=False):
  if width<=0 or height<=0 or len(focus)!=2 or any(not 0<=v<=1 for v in focus):raise ValueError('Invalid image window or focus')
  key=(str(path),width,height,tuple(focus),bool(spread))
  if key in self.prepared:return self.prepared[key]
  with Image.open(path) as original:im=ImageOps.exif_transpose(original).convert('RGB')
  scale=max(width/im.width,height/im.height);ppi=72/scale
  if ppi<self.config['minimum_ppi']:raise ValueError(f'Image too small for this window: {ppi:.1f} ppi; use a smaller image module or higher resolution')
  if ppi<self.config['recommended_ppi']:self.warnings.append(f'Image below recommended resolution: {Path(path).name}, {ppi:.1f} ppi')
  # Never upscale pixels. Crop once to the full spread window, then clip each half.
  target_scale=min(self.config['target_ppi']/72,1/scale)
  pixels=(max(1,round(width*target_scale)),max(1,round(height*target_scale)))
  cropped=ImageOps.fit(im,pixels,method=Image.Resampling.LANCZOS,centering=tuple(focus))
  buffer=io.BytesIO();cropped.save(buffer,format='JPEG',quality=self.config['jpeg_quality'],optimize=True);buffer.seek(0)
  result=ImageReader(buffer);self.prepared[key]=result
  a=self.by_path.get(str(Path(path).resolve()),{});digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
  self.images.append({'asset_id':a.get('id'),'sha256':digest,'source_pixels':[im.width,im.height],'embedded_pixels':list(pixels),'effective_ppi':round(ppi,1),'window_pt':[width,height]})
  # Protected bounds are optional source-normalized subject rectangles, supplied after visual inspection.
  cw,ch=width/scale,height/scale;left=(im.width-cw)*focus[0];top=(im.height-ch)*focus[1]
  for box in a.get('protected_bounds',[]):
   if len(box)!=4 or not 0<=box[0]<box[2]<=1 or not 0<=box[1]<box[3]<=1:raise ValueError('Invalid protected_bounds')
   x0,y0,x1,y1=box[0]*im.width,box[1]*im.height,box[2]*im.width,box[3]*im.height
   if x0<left or x1>left+cw or y0<top or y1>top+ch:self.warnings.append(f'Protected subject cropped: {a.get("id")}')
   if spread and x0<left+cw/2<x1:self.warnings.append(f'Protected subject crosses spread seam: {a.get("id")}')
  return result
 def sources_blocks(self):
  blocks=[{'type':'kicker','text':'素材记录 / 来源与许可'},{'type':'h1','text':'图片从哪里来。'}]
  for a in self.used.values():
   kind_label={'photo':'真实网络照片','user_photo':'用户实拍','ai_cover':'AI原创封面插画','graphic':'信息图／明确标注的图形'}[a['kind']]
   blocks.extend([{'type':'h2','text':a['subject']},{'type':'body','text':f"作者：{a['author']}。类型：{kind_label}。许可／使用依据：{a['license']}。"}])
   if a.get('date'):blocks.append({'type':'small','text':'拍摄时间：'+a['date']})
   if a.get('changes'):blocks.append({'type':'small','text':'修改：'+a['changes']})
   for key,label in [('source_url','原始来源'),('license_url','许可详情')]:
    if a.get(key):blocks.append({'type':'small','text':label+'：'+a[key],'link':a[key]})
  return blocks
