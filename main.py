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

# ========== DISCORD BOT SETUP ==========
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN not found")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== FASTAPI WEB SERVER (for cron job) ==========
web_app = FastAPI()

@web_app.get("/ping")
async def ping():
    """Cron job endpoint to check if bot is alive"""
    return {
        "status": "alive",
        "bot_running": bot.is_ready(),
        "timestamp": datetime.now().isoformat(),
        "guilds": len(bot.guilds) if bot.is_ready() else 0
    }

@web_app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}

def run_web_server():
    """Run FastAPI server in a separate thread"""
    uvicorn.run(web_app, host="0.0.0.0", port=8000)

# ========== DISCORD BOT COMMANDS ==========
@bot.event
async def on_ready():
    print(f"✅ Discord bot logged in as {bot.user}")
    print(f"✅ Web server running on port 8000")
    print(f"✅ Cron job endpoint: https://your-app.onrender.com/ping")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Error: {e}")

@bot.tree.command(name="ping", description="Returns Pong!")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

@bot.tree.command(name="generate", description="Generate 3D video from your images")
@app_commands.describe(time="Video duration in seconds (default 5)")
async def generate(interaction: discord.Interaction, time: float = 5):
    
    await interaction.response.send_message(
        "🎬 **Send me 2 images as attachments**\n"
        "1️⃣ Main image (front)\n2️⃣ Secondary image (sides)\n\n"
        "You have 60 seconds!",
        ephemeral=False
    )
    
    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and len(m.attachments) >= 2
    
    try:
        msg = await bot.wait_for("message", timeout=60, check=check)
        attachments = msg.attachments[:2]
        
        main_url = attachments[0].url
        small_url = attachments[1].url
        
        await interaction.followup.send(f"🔄 Generating {time} second video...")
        
        video_path = await render_3d_video(main_url, small_url, time)
        video_link = await upload_to_catbox(video_path)
        
        await interaction.followup.send(
            f"✅ **Video Ready!**\n"
            f"⏱️ Duration: {time} seconds\n"
            f"🔗 [Download Video]({video_link})"
        )
        
        os.remove(video_path)
        
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ Timeout!")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

async def upload_to_catbox(file_path):
    async with aiohttp.ClientSession() as session:
        with open(file_path, 'rb') as f:
            form = aiohttp.FormData()
            form.add_field('reqtype', 'fileupload')
            form.add_field('fileToUpload', f, filename=os.path.basename(file_path))
            async with session.post('https://catbox.moe/user/api.php', data=form) as resp:
                return await resp.text()

async def render_3d_video(main_image_url, small_image_url, duration_seconds):
    """Generate 3D video with images from Discord CDN"""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ margin: 0; overflow: hidden; }}
            canvas {{ width: 100%; height: 100%; }}
        </style>
    </head>
    <body>
        <canvas id="c"></canvas>
        <script type="importmap">
            {{
                "imports": {{
                    "three": "https://unpkg.com/three@0.128.0/build/three.module.js",
                    "three/addons/": "https://unpkg.com/three@0.128.0/examples/jsm/"
                }}
            }}
        </script>
        <script type="module">
            import * as THREE from "three";
            import {{ OrbitControls }} from "three/addons/controls/OrbitControls.js";
            
            const DURATION = {duration_seconds};
            const MAIN_IMG = "{main_image_url}";
            const SMALL_IMG = "{small_image_url}";
            
            const canvas = document.getElementById("c");
            const renderer = new THREE.WebGLRenderer({{ canvas, preserveDrawingBuffer: true, antialias: true }});
            renderer.setSize(720, 720);
            
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0a0a2a);
            
            const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
            camera.position.set(3, 3, 5);
            
            const ambientLight = new THREE.AmbientLight(0x404060);
            scene.add(ambientLight);
            const mainLight = new THREE.DirectionalLight(0xffffff, 1);
            mainLight.position.set(5, 10, 7);
            scene.add(mainLight);
            
            const geometry = new THREE.BoxGeometry(1.8, 1.8, 1.8);
            const textureLoader = new THREE.TextureLoader();
            
            const mainTexture = await textureLoader.loadAsync(MAIN_IMG);
            const smallTexture = await textureLoader.loadAsync(SMALL_IMG);
            
            const materials = [
                new THREE.MeshStandardMaterial({{ map: mainTexture }}),
                new THREE.MeshStandardMaterial({{ map: smallTexture }}),
                new THREE.MeshStandardMaterial({{ map: mainTexture }}),
                new THREE.MeshStandardMaterial({{ map: smallTexture }}),
                new THREE.MeshStandardMaterial({{ map: mainTexture }}),
                new THREE.MeshStandardMaterial({{ map: smallTexture }})
            ];
            
            const cube = new THREE.Mesh(geometry, materials);
            scene.add(cube);
            
            // Spinning spheres around cube
            const sphereGroup = new THREE.Group();
            for (let i = 0; i < 12; i++) {{
                const sphere = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 16), new THREE.MeshStandardMaterial({{ color: 0xff6600 }}));
                const angle = (i / 12) * Math.PI * 2;
                sphere.position.x = Math.cos(angle) * 1.5;
                sphere.position.z = Math.sin(angle) * 1.5;
                sphere.position.y = Math.sin(angle * 2) * 0.8;
                sphereGroup.add(sphere);
            }}
            scene.add(sphereGroup);
            
            const gridHelper = new THREE.GridHelper(10, 20, 0x88aaff, 0x335588);
            gridHelper.position.y = -1.2;
            scene.add(gridHelper);
            
            const controls = new OrbitControls(camera, canvas);
            controls.enableDamping = true;
            controls.autoRotate = true;
            controls.autoRotateSpeed = 2;
            controls.enableZoom = false;
            
            const stream = canvas.captureStream(30);
            const chunks = [];
            const recorder = new MediaRecorder(stream, {{ mimeType: 'video/webm', videoBitsPerSecond: 3000000 }});
            
            recorder.ondataavailable = e => {{
                if (e.data.size) chunks.push(e.data);
            }};
            
            let startTime = performance.now();
            
            function animate() {{
                const elapsed = (performance.now() - startTime) / 1000;
                if (elapsed >= DURATION) {{
                    recorder.stop();
                    return;
                }}
                
                cube.rotation.x = elapsed * 1.2;
                cube.rotation.y = elapsed * 1.8;
                sphereGroup.rotation.y = elapsed * 0.8;
                
                const scale = 1 + Math.sin(elapsed * 5) * 0.03;
                cube.scale.set(scale, scale, scale);
                
                controls.update();
                renderer.render(scene, camera);
                requestAnimationFrame(animate);
            }}
            
            recorder.start();
            animate();
            
            recorder.onstop = async () => {{
                const blob = new Blob(chunks, {{ type: 'video/webm' }});
                const buffer = await blob.arrayBuffer();
                window.videoData = Array.from(new Uint8Array(buffer));
            }};
        </script>
    </body>
    </html>
    """
    
    html_path = f"temp_{datetime.now().timestamp()}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--use-gl=swiftshader'])
        page = await browser.new_page()
        await page.goto(f"file://{os.path.abspath(html_path)}")
        await asyncio.sleep(duration_seconds + 2)
        video_array = await page.evaluate("window.videoData")
        await browser.close()
    
    video_path = f"video_{datetime.now().timestamp()}.webm"
    with open(video_path, "wb") as f:
        f.write(bytes(video_array))
    
    os.remove(html_path)
    return video_path

# ========== START BOTH SERVERS ==========
if __name__ == "__main__":
    # Start web server in background thread
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # Start Discord bot
    bot.run(TOKEN)
