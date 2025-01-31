from typing import Sequence

import numpy as np
import PIL
import torch
from einops import rearrange, repeat
from PIL import Image, ImageDraw, ImageFont

from imaginairy.paths import PKG_ROOT
from imaginairy.schema import LazyLoadingImage
from imaginairy.utils import get_device


def pillow_fit_image_within(
    image: PIL.Image.Image, max_height=512, max_width=512, convert="RGB", snap_size=8
):
    image = image.convert(convert)
    w, h = image.size
    resize_ratio = 1
    if w > max_width or h > max_height:
        resize_ratio = min(max_width / w, max_height / h)
    elif w < max_width and h < max_height:
        # it's smaller than our target image, enlarge
        resize_ratio = max(max_width / w, max_height / h)

    if resize_ratio != 1:
        w, h = int(w * resize_ratio), int(h * resize_ratio)
    # resize to integer multiple of snap_size
    w -= w % snap_size
    h -= h % snap_size

    if (w, h) != image.size:
        image = image.resize((w, h), resample=Image.Resampling.LANCZOS)
    return image


def pillow_img_to_torch_image(img: PIL.Image.Image):
    img = img.convert("RGB")
    img = np.array(img).astype(np.float32) / 255.0
    img = img[None].transpose(0, 3, 1, 2)
    img = torch.from_numpy(img)
    return 2.0 * img - 1.0


def torch_img_to_pillow_img(img: torch.Tensor):
    img = rearrange(img, "b c h w -> b h w c")
    img = torch.clamp((img + 1.0) / 2.0, min=0.0, max=1.0)
    img = (255.0 * img).cpu().numpy().astype(np.uint8)
    img = Image.fromarray(img[0])
    return img


def pillow_img_to_opencv_img(img: PIL.Image.Image):
    open_cv_image = np.array(img)
    # Convert RGB to BGR
    open_cv_image = open_cv_image[:, :, ::-1].copy()
    return open_cv_image


def model_latents_to_pillow_imgs(latents: torch.Tensor) -> Sequence[PIL.Image.Image]:
    from imaginairy.model_manager import get_current_diffusion_model  # noqa

    model = get_current_diffusion_model()
    latents = model.decode_first_stage(latents)
    latents = torch.clamp((latents + 1.0) / 2.0, min=0.0, max=1.0)
    imgs = []
    for latent in latents:
        latent = 255.0 * rearrange(latent.cpu().numpy(), "c h w -> h w c")
        img = Image.fromarray(latent.astype(np.uint8))
        imgs.append(img)
    return imgs


def pillow_img_to_model_latent(model, img, batch_size=1, half=True):
    # init_image = pil_img_to_torch(img, half=half).to(device)
    init_image = pillow_img_to_torch_image(img).to(get_device())
    init_image = repeat(init_image, "1 ... -> b ...", b=batch_size)
    if half:
        return model.get_first_stage_encoding(
            model.encode_first_stage(init_image.half())
        )
    return model.get_first_stage_encoding(model.encode_first_stage(init_image))


def imgpaths_to_imgs(imgpaths):
    imgs = []
    for imgpath in imgpaths:
        if isinstance(imgpath, str):
            img = LazyLoadingImage(filepath=imgpath)
            imgs.append(img)
        else:
            imgs.append(imgpath)

    return imgs


def add_caption_to_image(
    img, caption, font_size=16, font_path=f"{PKG_ROOT}/data/DejaVuSans.ttf"
):
    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype(font_path, font_size)

    x = 15
    y = img.height - 15 - font_size

    draw.text(
        (x, y),
        caption,
        font=font,
        fill=(255, 255, 255),
        stroke_width=3,
        stroke_fill=(0, 0, 0),
    )
