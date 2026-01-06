import argparse
import json
from src.service import FaceService


def main():
    parser = argparse.ArgumentParser(description="AI 考勤系统 (CLI 模式)")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 注册命令
    # python main.py reg -p "jack.jpg" -i "101" -n "Jack"
    p_reg = subparsers.add_parser("reg", help="注册员工")
    p_reg.add_argument("-p", "--path", required=True, help="相对路径 (在 staff_images 下)")
    p_reg.add_argument("-i", "--id", required=True, help="工号")
    p_reg.add_argument("-n", "--name", required=True, help="姓名")

    # 识别命令
    # python main.py run -p "test.jpg"
    p_run = subparsers.add_parser("run", help="识别图片")
    p_run.add_argument("-p", "--path", required=True, help="相对路径 (在 inputs 下)")

    args = parser.parse_args()

    # 加载配置与服务
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)

    try:
        service = FaceService(cfg)

        if args.command == "reg":
            res = service.register_staff(args.path, args.id, args.name)
            print(f"✅ 注册结果: {res}")

        elif args.command == "run":
            res = service.recognize_image(args.path)
            print("📸 识别结果:")
            print(json.dumps(res, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ 执行失败: {e}")


if __name__ == "__main__":
    main()