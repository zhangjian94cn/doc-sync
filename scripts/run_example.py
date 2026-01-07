import os
import sys
import subprocess

def main():
    print("=" * 50)
    print("   Doc Sync - 示例运行脚本")
    print("=" * 50)
    
    # Check if sync_config.json exists (New Config System)
    if not os.path.exists("sync_config.json"):
        print("❌ 未检测到 sync_config.json 配置文件。")
        print("请参考 README.md 创建配置文件并填入你的飞书 App ID 和 Secret。")
        return

    example_dir = os.path.abspath("examples/sample_vault")
    if not os.path.exists(example_dir):
        print(f"❌ 示例目录不存在: {example_dir}")
        return

    # Ensure assets directory and demo image exist
    assets_dir = os.path.join(example_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    image_path = os.path.join(assets_dir, "demo_image.png")
    
    if not os.path.exists(image_path):
        print(f"🎨 正在生成示例图片: {image_path}")
        # 1x1 Red Pixel PNG
        valid_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
        with open(image_path, "wb") as f:
            f.write(valid_png)

    print(f"📂 示例数据目录: {example_dir}")
    
    # Allow token as command line argument
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        print("\n请输入目标飞书文件夹 Token (直接回车将使用 'root' 根目录):")
        print("提示: 建议创建一个新文件夹并粘贴其 Token，以免混淆根目录文件。")
        token = input("Target Cloud Token [root]: ").strip()
    
    if not token:
        token = "root"
    
    print(f"\n🚀 准备同步到云端: {token}")
    print("正在启动同步进程...\n")
    
    # Construct command
    cmd = [sys.executable, "main.py", example_dir, token, "--force"]
    
    try:
        subprocess.run(cmd, check=True)
        print("\n✅ 示例运行完成！请前往飞书查看效果。")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 运行失败: {e}")
    except KeyboardInterrupt:
        print("\n⚠️ 用户取消。")

if __name__ == "__main__":
    main()
