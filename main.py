import discord
from discord.ext import commands
from playwright.async_api import async_playwright
import asyncio
import aiohttp
import os
from datetime import datetime

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

if not TOKEN:
    raise ValueError("❌ DISCORD_BOT_TOKEN not found in environment variables!")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

async def upload_to_catbox(file_path):
    """Upload video to catbox.moe"""
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
            renderer.setPixelRatio(window.devicePixelRatio);
            
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0a0a2a);
            scene.fog = new THREE.FogExp2(0x0a0a2a, 0.008);
            
            const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
            camera.position.set(3, 3, 5);
            camera.lookAt(0, 0, 0);
            
            const ambientLight = new THREE.AmbientLight(0x404060);
            scene.add(ambientLight);
            
            const mainLight = new THREE.DirectionalLight(0xffffff, 1);
            mainLight.position.set(5, 10, 7);
            scene.add(mainLight);
            
            const backLight = new THREE.PointLight(0x4466ff, 0.5);
            backLight.position.set(-2, 1, -3);
            scene.add(backLight);
            
            const geometry = new THREE.BoxGeometry(1.8, 1.8, 1.8);
            const textureLoader = new THREE.TextureLoader();
            
            const mainTexture = await textureLoader.loadAsync(MAIN_IMG);
            const smallTexture = await textureLoader.loadAsync(SMALL_IMG);
            
            const materials = [
                new THREE.MeshStandardMaterial({{ map: mainTexture, roughness: 0.3, metalness: 0.1 }}),
                new THREE.MeshStandardMaterial({{ map: smallTexture, roughness: 0.3, metalness: 0.1 }}),
                new THREE.MeshStandardMaterial({{ map: mainTexture, roughness: 0.3, metalness: 0.1 }}),
                new THREE.MeshStandardMaterial({{ map: smallTexture, roughness: 0.3, metalness: 0.1 }}),
                new THREE.MeshStandardMaterial({{ map: mainTexture, roughness: 0.3, metalness: 0.1 }}),
                new THREE.MeshStandardMaterial({{ map: smallTexture, roughness: 0.3, metalness: 0.1 }})
            ];
            
            const cube = new THREE.Mesh(geometry, materials);
            scene.add(cube);
            
            const sphereGroup = new THREE.Group();
            const sphereMat = new THREE.MeshStandardMaterial({{ color: 0xff6600, emissive: 0x441100 }});
            
            for (let i = 0; i < 12; i++) {{
                const sphere = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 16), sphereMat);
                const angle = (i / 12) * Math.PI * 2;
                const radius = 1.5;
                sphere.position.x = Math.cos(angle) * radius;
                sphere.position.z = Math.sin(angle) * radius;
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
            controls.enablePan = false;
            
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
                sphereGroup.rotation.x = Math.sin(elapsed * 0.5) * 0.3;
                
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

@bot.command(name="generate")
async def generate_video(ctx, time: float = 5):
    """!generate 10"""
    
    embed = discord.Embed(
        title="🎬 3D Video Generator",
        description="**Send 2 images:**\n1. Main image (front face)\n2. Secondary image (side faces)\n\nSend images as **attachments**",
        color=discord.Color.blue()
    )
    
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and len(m.attachments) > 0
    
    try:
        msg1 = await bot.wait_for("message", timeout=60, check=check)
        main_attachment = msg1.attachments[0]
        main_url = main_attachment.url
        
        await ctx.send("✅ First image received! Send the second image...")
        
        msg2 = await bot.wait_for("message", timeout=60, check=check)
        small_attachment = msg2.attachments[0]
        small_url = small_attachment.url
        
        await ctx.send(f"🎬 Generating 3D video for {time} seconds...\n⏳ Please wait...")
        
        video_path = await render_3d_video(main_url, small_url, time)
        
        await ctx.send("📤 Uploading video...")
        video_link = await upload_to_catbox(video_path)
        
        embed_result = discord.Embed(
            title="✅ Video Generated!",
            description=f"**Duration:** {time} seconds\n[🎥 Download Video]({video_link})",
            color=discord.Color.green()
        )
        embed_result.set_footer(text="Thanks for using the bot 🤍")
        
        await ctx.send(embed=embed_result)
        
        os.remove(video_path)
        
    except asyncio.TimeoutError:
        await ctx.send("❌ Timeout! Try again.")
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    bot.run(TOKEN)
