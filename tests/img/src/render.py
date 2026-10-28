"""mermaid-исходники → PNG: headless Chrome рисует страницу, PIL обрезает белые поля."""
import subprocess, sys, pathlib
from PIL import Image, ImageChops
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = pathlib.Path(sys.argv[1])
TPL = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#fff;font-family:Arial,Helvetica,sans-serif}#d{padding:24px;display:inline-block}svg{max-width:none!important}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script></head><body><div id="d"><pre class="mermaid">
%s
</pre></div><script>mermaid.initialize({startOnLoad:false,theme:'base',flowchart:{curve:'basis',htmlLabels:true,nodeSpacing:30,rankSpacing:44,padding:12},
themeVariables:{fontFamily:'Arial',fontSize:'16px',primaryColor:'#E3EBFD',primaryBorderColor:'#0E41D2',primaryTextColor:'#2D3137',lineColor:'#5B6270',tertiaryColor:'#F2F3F5'}});
mermaid.run().then(()=>{for(const svg of document.querySelectorAll('svg')){const vb=svg.viewBox.baseVal;
svg.removeAttribute('style');svg.setAttribute('width',vb.width);svg.setAttribute('height',vb.height)}})</script></body></html>"""
for src in sorted(pathlib.Path(".").glob("*.mmd")):
    html = src.with_suffix(".html"); html.write_text(TPL % src.read_text(), encoding="utf-8")
    png = OUT / (src.stem + ".png")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    "--window-size=3000,3600", "--virtual-time-budget=8000", f"--screenshot={png}", html.resolve().as_uri()],
                   check=True, capture_output=True)
    box = ImageChops.difference(im, Image.new("RGB", im.size, "white")).getbbox()
    im.crop((max(box[0]-30,0), max(box[1]-30,0), min(box[2]+30,im.width), min(box[3]+30,im.height))).save(png, optimize=True)
    print(png, Image.open(png).size)
