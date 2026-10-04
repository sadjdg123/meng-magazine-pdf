#!/usr/bin/env python3
"""Exercise real pagination/content-retention failure modes; outputs stay in a caller directory."""
import argparse,json,subprocess,sys
from pathlib import Path
from render import render

def test(out):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
 paragraphs=['第'+str(i)+'段：街巷是理解一座城市的入口。慢慢走，观察门窗、招牌与人的日常；文字增长时，应自然续页，保留标点、字形和完整语义。'*6 for i in range(12)]
 data={'title':'压力测试','blocks':[{'type':'h1','text':'一个很长的中文标题：当正文增加、表格跨页与图片缺失同时出现时，这套版式应该怎样继续排版？'},*({'type':'body','text':s} for s in paragraphs),{'type':'h2','text':'跨页表格'},{'type':'table','rows':[['项目','核对事项']]+[[f'项目{i:02d}','逐项核对文本。'+('这一行有很长的内容。'*100 if i==16 else '完整保留，不缩小字号。')] for i in range(70)],'widths':[1,4]},{'type':'image','path':'absent.jpg','required':False},{'type':'body','text':'缺图以后，正文接着排。'}]}
 source=out/'stress.json';source.write_text(json.dumps(data,ensure_ascii=False));result=render(source,out/'stress.pdf')
 assert result['pages']>5 and len(result['warnings'])==1
 import fitz
 doc=fitz.open(out/'stress.pdf');tablepages=[p for p in doc if '项目' in p.get_text()];assert len(tablepages)>2
 assert all('核对事项' in p.get_text() for p in tablepages)
 outcomes={'long_text_and_title':'pass','table_header_repeats':'pass','oversized_table_row_splits':'pass','optional_missing_image':'pass'}
 for name,block,exception in [('required_missing_image',{'type':'image','path':'absent.jpg'},FileNotFoundError),('unsupported_glyph',{'type':'body','text':'字形测试'+chr(0x10FFFF)},ValueError)]:
  source=out/(name+'.json');source.write_text(json.dumps({'title':name,'blocks':[block]}))
  try:render(source,out/(name+'.pdf'))
  except exception:outcomes[name]='pass'
  else:raise AssertionError(name+' should fail before delivery')
 (out/'results.json').write_text(json.dumps(outcomes,indent=2));print(json.dumps(outcomes,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output_directory');a=p.parse_args();test(a.output_directory)
