import discord
from discord.ext import commands
from discord import app_commands
from playwright.async_api import async_playwright
import asyncio
import aiohttp
import os
from datetime import datetime
from fastapi import FastAPI
import uvicorn
import threading

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

if not TOKEN:
    print("NO TOKEN FOUND")
    exit(1)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# FASTAPI WEB SERVER
web_app = FastAPI()

@web_app.get("/ping")
async def ping():
    return {"status": "alive", "bot_running": bot.is_ready(), "timestamp": datetime.now().isoformat()}

@web_app.get("/health")
async def health():
    return {"status": "healthy"}

def run_web():
    uvicorn.run(web_app, host="0.0.0.0", port=8000)

# DISCORD BOT
@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")
    await bot.tree.sync()
    print("Commands synced")

@bot.tree.command(name="ping", description="Returns Pong!")
async def cmd_ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

@bot.tree.command(name="generate", description="Generate 3D video")
@app_commands.describe(seconds="Video duration in seconds")
async def cmd_generate(interaction: discord.Interaction, seconds: float = 5):
    await interaction.response.send_message("Send 2 images as attachments. You have 60 seconds.")
    
    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and len(m.attachments) >= 2
    
    try:
        msg = await bot.wait_for("message", timeout=60, check=check)
        main_url = msg.attachments[0].url
        small_url = msg.attachments[1].url
        
        await interaction.followup.send(f"Generating {seconds} second video...")
        
        video_path = await render_video(main_url, small_url, seconds)
        video_link = await upload_to_catbox(video_path)
        
        await interaction.followup.send(f"✅ Video ready!\n{video_link}")
        os.remove(video_path)
        
    except asyncio.TimeoutError:
        await interaction.followup.send("Timeout!")
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

async def upload_to_catbox(file_path):
    async with aiohttp.ClientSession() as session:
        with open(file_path, 'rb') as f:
            form = aiohttp.FormData()
            form.add_field('reqtype', 'fileupload')
            form.add_field('fileToUpload', f, filename=os.path.basename(file_path))
            async with session.post('https://catbox.moe/user/api.php', data=form) as resp:
                return await resp.text()

async def render_video(main_img, small_img, duration):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><style>body{{margin:0;overflow:hidden}}</style></head>
    <body>
    <canvas id="c"></canvas>
    <script type="importmap">
        {{"imports":{{"three":"https://unpkg.com/three@0.128.0/build/three.module.js"}}}}
    </script>
    <script type="module">
        import * as THREE from "three";
        const canvas = document.getElementById("c");
        const renderer = new THREE.WebGLRenderer({{canvas, preserveDrawingBuffer:true}});
        renderer.setSize(720,720);
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0a0a2a);
        const camera = new THREE.PerspectiveCamera(45,1,0.1,1000);
        camera.position.set(3,3,5);
        const light = new THREE.DirectionalLight(0xffffff,1);
        light.position.set(5,10,7);
        scene.add(light);
        scene.add(new THREE.AmbientLight(0x404060));
        const geometry = new THREE.BoxGeometry(1.8,1.8,1.8);
        const loader = new THREE.TextureLoader();
        const mainTex = await loader.loadAsync("{main_img}");
        const smallTex = await loader.loadAsync("{small_img}");
        const mats = [
            new THREE.MeshStandardMaterial({{map:mainTex}}),
            new THREE.MeshStandardMaterial({{map:smallTex}}),
            new THREE.MeshStandardMaterial({{map:mainTex}}),
            new THREE.MeshStandardMaterial({{map:smallTex}}),
            new THREE.MeshStandardMaterial({{map:mainTex}}),
            new THREE.MeshStandardMaterial({{map:smallTex}})
        ];
        const cube = new THREE.Mesh(geometry,mats);
        scene.add(cube);
        const stream = canvas.captureStream(30);
        const chunks = [];
        const recorder = new MediaRecorder(stream,{{mimeType:'video/webm'}});
        recorder.ondataavailable = e => {{if(e.data.size) chunks.push(e.data);}};
        const start = performance.now();
        function animate(){{
            const elapsed = (performance.now()-start)/1000;
            if(elapsed>={duration}){{
                recorder.stop();
                return;
            }}
            cube.rotation.x = elapsed*1.2;
            cube.rotation.y = elapsed*1.8;
            renderer.render(scene,camera);
            requestAnimationFrame(animate);
        }}
        recorder.start();
        animate();
        recorder.onstop = async()=>{{
            const blob = new Blob(chunks,{{type:'video/webm'}});
            window.result = Array.from(new Uint8Array(await blob.arrayBuffer()));
        }};
    </script>
    </body>
    </html>
    """
    path = f"temp_{datetime.now().timestamp()}.html"
    with open(path, "w") as f:
        f.write(html)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"file://{os.path.abspath(path)}")
        await asyncio.sleep(duration + 2)
        data = await page.evaluate("window.result")
        await browser.close()
    
    os.remove(path)
    vid_path = f"video_{datetime.now().timestamp()}.webm"
    with open(vid_path, "wb") as f:
        f.write(bytes(data))
    return vid_path

if __name__ == "__main__":
    t = threading.Thread(target=run_web, daemon=True)
    t.start()
    bot.run(TOKEN)
