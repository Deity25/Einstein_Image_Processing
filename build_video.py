#!/usr/bin/env python3
"""Rebuild the narrated tutorial: Pillow + OpenCV + local espeak + ffmpeg.

This is a *tutorial-building tool*, not required to run the offline assistant.
It uses the included spritesheet and never calls an internet service.
"""

import io
import math
import subprocess
import tempfile
import textwrap
import wave
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parents[2] / 'Einstein_Offline_Engineering_Video.mp4'
ATLAS = Image.open(ROOT/'assets'/'spritesheet.webp').convert('RGBA')
W,H,FPS = 1280,720,15
FONT='/usr/share/fonts/opentype/inter/Inter-Regular.otf'
BOLD='/usr/share/fonts/opentype/inter/Inter-Bold.otf'
MONO='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'

def font(size, bold=False, mono=False):
    return ImageFont.truetype(MONO if mono else BOLD if bold else FONT, size)

def label(draw, xy, txt, size=22, color='#f7faff', bold=False, mono=False):
    draw.text(xy, txt, font=font(size,bold,mono), fill=color)

def rr(d, bbox, fill, radius=16, outline=None, width=2):
    d.rounded_rectangle(bbox, radius, fill=fill, outline=outline, width=width)

def multiline(d, x,y,text,size=23,color='#dce6f9',width=790,spacing=9,bold=False):
    f=font(size,bold)
    lines=[]
    for p in text.split('\n'):
        words=p.split(' ');acc=''
        for w in words:
            try_it=(acc+' '+w).strip()
            if d.textbbox((0,0),try_it,font=f)[2]>width and acc:
                lines.append(acc);acc=w
            else:acc=try_it
        lines.append(acc)
    for l in lines:
        d.text((x,y),l,font=f,fill=color)
        y+=size+spacing
    return y

def code_box(d, lines, x=72,y=256,w=805,active=None):
    h=42*len(lines)+34
    rr(d,(x,y,x+w,y+h),'#0e1728',16,outline='#334a66')
    for i,line in enumerate(lines):
        if active is not None and active==i:
            rr(d,(x+14,y+17+i*42,x+w-14,y+54+i*42),'#164f54',9)
        label(d,(x+23,y+20+i*42),f'{i+1:02d}',16,'#68849a',mono=True)
        label(d,(x+70,y+18+i*42),line,19,'#c1f6ed' if i==active else '#e2eafd',mono=True)
    return y+h

def stage(d,title,caption,n,total):
    label(d,(66,29),'EINSTEIN  /  OFFLINE AI ENGINEERING',19,'#6ddecf',True)
    label(d,(1094,30),f'{n:02d} / {total:02d}',18,'#9db6ce',True)
    d.line((65,67,1215,67),fill='#28435a',width=2)
    label(d,(66,95),title,40,'#f9faff',True)
    multiline(d,70,156,caption,21,'#9fb6d0',width=860)

def chip(d,x,y,t,color='#276e67',w=None):
    w=w or max(130, len(t)*12+40)
    rr(d,(x,y,x+w,y+42),'#142536',14,outline=color)
    label(d,(x+17,y+9),t,18,'#b8f9ec',True)

def frame_sprite(row,col,scale=(235,254)):
    cell=ATLAS.crop((col*192,row*208,(col+1)*192,(row+1)*208))
    return cell.resize(scale, Image.Resampling.LANCZOS)

SCENES = [
    dict(title='An animated pet is not an AI model',
         subtitle='Four pieces work together to make a private desktop companion.',
         narration='Einstein has four main components. The sprite is the moving character. Your browser is the interface. Python coordinates requests. Ollama answers questions, while SQLite remembers what you choose to save.', row=0),
    dict(title='A sprite sheet produces movement',
         subtitle='A fixed grid holds tiny images, played rapidly like a flipbook.',
         narration='The pet artwork is stored in one transparent image. Each cell is one hundred ninety two by two hundred eight pixels. JavaScript changes the row and column to animate walking, thinking, resting, or celebrating.', row=1),
    dict(title='JavaScript runs the pet state machine',
         subtitle='Animation, dialogue bubbles, and user interactions run in the browser.',
         narration='JavaScript remembers the current animation state. A timer advances the frame. When you send a question the pet switches to working. When an answer returns, it celebrates. If a request fails, it enters debugging mode.', row=7),
    dict(title='Python listens only on your Mac',
         subtitle='The browser communicates with a local HTTP server, not a cloud service.',
         narration='Python starts a server on the loopback address, one two seven dot zero dot zero dot one. It accepts chat messages, reads selected documents, looks up saved memory, and contacts Ollama on the same laptop.', row=8),
    dict(title='Ollama is the local AI brain',
         subtitle='One-time download; responses are generated on your own machine.',
         narration='First, install Ollama and download a model while you have internet. After setup, the Python program sends local chat requests to port eleven four three four. It does not need an online API key.', row=7),
    dict(title='SQLite makes memory persistent',
         subtitle='Notes, document passages, and previous conversations survive restarts.',
         narration='SQLite is a single database file on your computer. Clicking Remember saves a note. Importing a document saves searchable passages. Your chat history is stored too, so the assistant keeps useful context between sessions.', row=0),
    dict(title='Documents are retrieved, not retrained',
         subtitle='The assistant searches your notes and adds matching text to the prompt.',
         narration='When you ask a question about a document, Python finds relevant text passages. These passages are included as context for the local model. This is retrieval augmented generation, not training new model weights.', row=8),
    dict(title='Einstein reacts to real app events',
         subtitle='Idle, working, success, error, and inactivity drive sprite animations.',
         narration='The character has separate animation rows. Idle means a gentle thinking loop. Sending a message starts working mode. A successful response triggers a jump. Errors trigger a debugging reaction, and inactivity starts resting mode.', row=4),
    dict(title='Run everything from Mac Terminal',
         subtitle='Use the bundled project, then open Einstein in your local browser.',
         narration='Install Ollama and download the model while online. Then extract the Einstein offline project. In Terminal, enter its folder and run python three server dot py. Open the localhost address in your browser.', row=1),
    dict(title='Offline, private, and under your control',
         subtitle='Your notes and imported files remain on your Mac.',
         narration='After the initial setup, Einstein can work without internet. You can import your own files and save or delete memories. A small model can make mistakes, and this starter project does not include voice control or a system wide floating window.', row=0),
]

def make_base(s, idx, total_duration):
    # Draw one static composition per scene; runtime overlays add motion.
    im=Image.new('RGB',(W,H),'#0a1120');d=ImageDraw.Draw(im)
    d.ellipse((-200,-230,580,480),fill='#102037')
    d.ellipse((700,140,1470,890),fill='#10243a')
    rr(d,(945,246,1215,558),'#15273c',30,outline='#2d5d66')
    stage(d,s['title'],s['subtitle'],idx+1,len(SCENES))
    if idx==0:
        cards=[('01','SPRITE SHEET','The visible character',75,248),('02','BROWSER UI','Buttons, animation, chat',488,248),('03','PYTHON SERVER','Processes your question',75,398),('04','OLLAMA + SQLITE','Answers and remembers',488,398)]
        for number,head,desc,x,y in cards:
            rr(d,(x,y,x+374,y+120),'#16263e',15,outline='#31536c')
            label(d,(x+18,y+18),number,22,'#58d5c5',True)
            label(d,(x+60,y+18),head,21,'#f7faff',True)
            label(d,(x+20,y+71),desc,18,'#b8c8db')
    if idx==1:
        rr(d,(70,247,904,448),'#15263c',17,outline='#36556c')
        for c in range(6):
            pic=frame_sprite(1,c,(98,107))
            im.paste(pic,(105+c*128,272),pic)
            label(d,(128+c*128,398),f'{c:02}',15,'#94a7bc',mono=True)
        code_box(d,['x = column * 192', 'y = row * 208'],75,469,810,0)
    if idx==2:
        code_box(d, [
            "const state = states[current];",
            "pet.style.backgroundPosition = `${-frame*192}px ...`",
            "frame = (frame + 1) % state.frames;",
            "setMode('success'); // after a response"
        ],70,254,828,1)
        chip(d,80,492,'IDLE    ->    WORKING    ->    SUCCESS',w=810)
    if idx==3:
        cards=[('BROWSER','http://127.0.0.1:8765',75),('PYTHON','server.py',360),('OLLAMA','127.0.0.1:11434',645)]
        for head,sub,x in cards:
            rr(d,(x,282,x+260,420),'#162a41',16,outline='#3b6874')
            label(d,(x+18,309),head,22,'#74e5d7',True)
            label(d,(x+16,361),sub,16,'#c2d6ec',mono=True)
        label(d,(325,329),'>',30,'#64e5d0',True)
        label(d,(611,329),'>',30,'#64e5d0',True)
        code_box(d,['HOST = "127.0.0.1"', 'ThreadingHTTPServer((HOST,PORT),Handler)'],75,463,825,0)
    if idx==4:
        code_box(d,['ollama pull qwen3:1.7b','OLLAMA_URL = "http://127.0.0.1:11434"','Request(OLLAMA_URL + "/api/chat", ...)','answer = response["message"]["content"]'],70,252,830,2)
        chip(d,80,478,'ONE-TIME DOWNLOAD    |    THEN DISCONNECT',w=800)
    if idx==5:
        rr(d,(70,248,903,457),'#15263b',17,outline='#345368')
        for i,(table,desc) in enumerate([('memories','Facts you explicitly save'),('documents','Chunks of imported files'),('chats','Your questions and answers')]):
            y=262+i*61
            chip(d,92,y,table.upper(),'#387b74',200)
            label(d,(321,y+10),desc,21,'#d7e5f2')
        code_box(d,['INSERT INTO memories(note, created_at)', 'VALUES (?, ?)   # Parameterized SQL'],70,483,830,0)
    if idx==6:
        cards=[('FILE','Read text'),('CHUNK','Split passages'),('SEARCH','Match keywords'),('PROMPT','Add context')]
        for i,(a,b) in enumerate(cards):
            x=70+i*209
            rr(d,(x,267,x+188,385),'#162b42',16,outline='#3c6d75')
            label(d,(x+15,294),a,19,'#75e4d7',True)
            label(d,(x+15,342),b,17,'#bfd0e1')
            if i<3:label(d,(x+192,312),'>',21,'#56daca',True)
        code_box(d,['sources = relevant_documents(question)', 'messages = make_messages(question)'],72,445,825,0)
    if idx==7:
        cards=[('IDLE','Thinking'),('WORK','Processing'),('SUCCESS','Jumping'),('ERROR','Debugging')]
        for i,(a,b) in enumerate(cards):
            x=72+i*205
            rr(d,(x,282,x+185,422),'#152941',16,outline='#375e77')
            label(d,(x+15,314),a,18,'#72e5d6',True)
            label(d,(x+15,372),b,17,'#d2e5f7')
        code_box(d,['setMode("work")', 'setMode("success", 3000)'],72,466,825,0)
    if idx==8:
        code_box(d,['ollama pull qwen3:1.7b', 'unzip Einstein_Offline_Assistant.zip', 'cd Einstein_Offline_Assistant', 'python3 server.py', 'open http://127.0.0.1:8765'],70,233,830,3)
    if idx==9:
        cards=[('NO CLOUD API','All app requests stay local',72,271),('YOUR DATA','~/.einstein_offline/einstein.sqlite3',72,405)]
        for head,sub,x,y in cards:
            rr(d,(x,y,x+828,y+114),'#142b3f',16,outline='#347e76')
            label(d,(x+25,y+16),head,24,'#7ee5da',True)
            label(d,(x+25,y+66),sub,20,'#dae7f5',mono=('sqlite3' in sub))
    # Right-side header above continuously animated Einstein.
    chip(d,967,218,'EINSTEIN',w=232)
    rr(d,(66,586,1214,687),'#111e31',16,outline='#2b4259')
    label(d,(85,601),'VOICEOVER / EXPLANATION',13,'#71cdbf',True)
    multiline(d,86,627,s['narration'],16,'#e7eefc',width=1100,spacing=5)
    return cv2.cvtColor(np.asarray(im),cv2.COLOR_RGB2BGR)

def overlay_rgba(frame, rgba,x,y):
    rgb=np.array(rgba,dtype=np.uint8)
    a=rgb[:,:,3:4].astype(np.float32)/255
    hh,ww=rgb.shape[:2]
    if x<0 or y<0 or y+hh>frame.shape[0] or x+ww>frame.shape[1]:return
    area=frame[y:y+hh,x:x+ww]
    source=rgb[:,:,:3][:,:,::-1]
    area[:]=(source*a+area*(1-a)).astype(np.uint8)

def make_video():
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        audios=[];durations=[]; rate=22050
        for i,s in enumerate(SCENES):
            dest=tmp/f'{i:02}.wav'
            subprocess.run(['espeak','-v','en-us+m3','-s','142','-a','150','-w',str(dest),s['narration']],check=True)
            with wave.open(str(dest),'rb') as w:
                count=w.getnframes();sr=w.getframerate();data=w.readframes(count)
                if w.getnchannels()!=1 or w.getsampwidth()!=2:
                    raise ValueError('Unexpected espeak audio format')
                if sr!=rate:
                    raise ValueError('Unexpected espeak sample rate')
                audios.append(data)
                # 1.1 seconds for scene transitions; speech ends before next scene.
                audios.append(bytes(round(rate*1.1)*2))
                durations.append(count/rate+1.1)
        rawvid=str(tmp/'silent.mp4')
        fourcc=cv2.VideoWriter_fourcc(*'mp4v')
        writer=cv2.VideoWriter(rawvid,fourcc,FPS,(W,H))
        if not writer.isOpened():raise RuntimeError('Cannot create video')
        total=sum(durations);passed=0
        sprites={}
        for row in [0,1,4,5,6,7,8]:
            sprites[row]=[frame_sprite(row,c,(235,254)) for c in range({0:6,1:8,4:5,5:8,6:6,7:6,8:6}[row])]
        for idx,(scene,duration) in enumerate(zip(SCENES,durations)):
            frames=round(duration*FPS)
            base=make_base(scene,idx,duration)
            for n in range(frames):
                t=n/FPS
                current=base.copy()
                row=scene['row']
                if idx==7:
                    row=[0,7,4,5][min(3,int(t/(duration/4)))]
                    highlight=min(3,int(t/(duration/4)))
                    cv2.rectangle(current,(72+highlight*205,282),(257+highlight*205,422),(89,232,164),3)
                if idx==1:
                    col=(int(t*3)%6)
                    cv2.rectangle(current,(96+col*128,268),(213+col*128,394),(104,236,207),3)
                if idx==6:
                    flash=int(t*2)%4
                    cv2.rectangle(current,(70+flash*209,267),(258+flash*209,385),(108,240,186),3)
                if idx==4:
                    active=int(t*1.6)%4
                    cv2.rectangle(current,(87,271+active*42),(880,309+active*42),(107,220,179),2)
                col=int(t*6)%len(sprites[row])
                sprite=sprites[row][col]
                bob=round(math.sin(t*5)*3)
                overlay_rgba(current,sprite,965,296+bob)
                elapsed=passed+t
                cv2.rectangle(current,(0,711),(W,720),(29,49,66),-1)
                cv2.rectangle(current,(0,711),(int(W*elapsed/total),720),(104,230,198),-1)
                writer.write(current)
            passed+=duration
            print('scene',idx+1,'of',len(SCENES),'rendered',round(duration,1),'sec',flush=True)
        writer.release()
        wavpath=str(tmp/'voice.wav')
        with wave.open(wavpath,'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate)
            w.writeframes(b''.join(audios))
        subprocess.run(['ffmpeg','-y','-v','error','-i',rawvid,'-i',wavpath,'-c:v','libx264','-crf','23','-preset','veryfast','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-shortest',str(OUT)],check=True)
    print('DONE',OUT,'size',OUT.stat().st_size,'seconds',round(total,1))

if __name__=='__main__':make_video()
