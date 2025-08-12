import os, io, base64, argparse, yaml, requests
from PIL import Image

def load_cfg(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def img_to_b64(path):
    with Image.open(path) as im:
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

def run_a1111(cfg, a_pass_image, face_mask_path, out_path):
    ep = cfg["general"]["a1111_endpoint"]
    bp = cfg["b_pass"]

    init_b64 = img_to_b64(a_pass_image)
    mask_b64 = img_to_b64(face_mask_path)

    payload = {
        "init_images": [init_b64],
        "mask": mask_b64,
        "prompt": bp["prompt"],
        "negative_prompt": bp["negative"],
        "denoising_strength": float(bp["denoise"]),
        "cfg_scale": float(bp["cfg"]),
        "steps": int(bp["steps"]),
        "sampler_name": bp.get("sampler", "DPM++ SDE Karras"),
        "inpainting_fill": 1,
        "inpaint_full_res": True,
        "inpaint_full_res_padding": 32,
        "inpainting_mask_invert": 0,
        "resize_mode": 0,
        "mask_blur": int(bp["mask_blur_px"]),
        "width": 0,
        "height": 0,
        "override_settings": {
            **({"sd_model_checkpoint": cfg["general"].get("model_checkpoint")} if cfg["general"].get("model_checkpoint") else {})
        },
        "override_settings_restore_afterwards": True,
    }
    if bool(bp.get("use_controlnet", False)):
        payload["alwayson_scripts"] = {
            "ControlNet": {
                "args": [{
                    "enabled": True,
                    "module": bp.get("controlnet_module", "softedge_hed"),
                    "model": bp.get("controlnet_model", ""),
                    "weight": float(bp.get("controlnet_weight", 0.75)),
                    "image": init_b64,
                    "resize_mode": 1,
                    "lowvram": False,
                    "processor_res": 512,
                    "threshold_a": 64,
                    "threshold_b": 64,
                    "guidance_start": 0.0,
                    "guidance_end": 1.0,
                    "control_mode": 1
                }]
            }
        }
    r = requests.post(f"{ep}/sdapi/v1/img2img", json=payload, timeout=600)
    r.raise_for_status()
    data = r.json()
    if "images" not in data or not data["images"]:
        raise RuntimeError("No images returned from A1111")
    out_b64 = data["images"][0].split(",",1)[-1]
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(out_b64))
    print(f"[B-PASS a1111] Saved: {out_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--workdir", default="work")
    ap.add_argument("--output", default="output")
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    a_pass_image = os.path.join(args.workdir, "a_pass", "base_enhanced.png")
    face_mask_path = os.path.join(args.workdir, "masks", "face_mask.png")
    os.makedirs(args.output, exist_ok=True)
    out_path = os.path.join(args.output, "final.png")

    run_a1111(cfg, a_pass_image, face_mask_path, out_path)

if __name__ == "__main__":
    main()