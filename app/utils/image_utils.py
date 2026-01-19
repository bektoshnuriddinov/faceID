import cv2

def add_margin(image, margin_ratio=0.05):
    h, w = image.shape[:2]

    top = int(h * margin_ratio)
    bottom = int(h * margin_ratio)
    left = int(w * margin_ratio)
    right = int(w * margin_ratio)

    color = [255, 255, 255]

    new_img = cv2.copyMakeBorder(
        image,
        top, bottom, left, right,
        borderType=cv2.BORDER_CONSTANT,
        value=color
    )

    return new_img