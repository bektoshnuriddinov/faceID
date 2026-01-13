from fastapi import APIRouter, Request, HTTPException, Body
from typing import Optional
from datetime import datetime
import os, cv2, numpy as np, base64, uuid
from app.services.database import client
from app.services.face_recognition import get_face_embedding
from fastapi.responses import JSONResponse
import asyncio
from app.utils.response import success, error
from app.utils.image_utils import add_margin

router = APIRouter()

async def run_in_executor(func, *args):
    return await asyncio.get_event_loop().run_in_executor(None, lambda: func(*args))

def save_image(img_bytes, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(img_bytes)

@router.post("/register-persons")
async def register_persons(
    request: Request,
    border_id:int = Body(...),
    sgb_person_id: int = Body(...),
    citizen: int = Body(...),
    citizen_sgb: int = Body(...),
    date_of_birth: str = Body(...),
    passport_number: str = Body(...),
    passport_expired: str = Body(...),
    sex: int = Body(...),
    full_name: str = Body(...),
    photo: Optional[str] = Body(None),
    reg_date: str = Body(...),
    direction_country: int = Body(...),
    direction_country_sgb: int = Body(...),
    action: int = Body(...),
    kpp: Optional[str] = Body(None),
    visa_type: Optional[str] = Body(None),
    visa_number: Optional[str] = Body(None),
    visa_organ:Optional[str] = Body(None),
    visa_date_from: Optional[str] = Body(None),
    visa_date_to: Optional[str] = Body(None)
):
    import time
    try:
        try:
            passport_expired_dt = datetime.strptime(passport_expired, "%Y-%m-%d").date()
            date_of_birth_dt = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
            reg_date_dt = datetime.strptime(reg_date, "%Y-%m-%d %H:%M:%S")
            visa_date_from = datetime.strptime(visa_date_from, "%Y-%m-%d").date() if visa_date_from else None
            visa_date_to = datetime.strptime(visa_date_to, "%Y-%m-%d").date() if visa_date_to else None
        except:
            return error("Invalid date format")

        exists = client.execute(
            "SELECT id FROM persons WHERE sgb_person_id = %(sgb)s",
            {"sgb": sgb_person_id}
        )
        if exists:
            return error("Person with this SGB ID already exists")
        img_path = None
        embedding = [0.0]*512

        if photo:
            if "base64," in photo:
                photo = photo.split("base64,")[1]
            try:
                img_bytes = base64.b64decode(photo)
            except:
                return error("Invalid base64 image")

            image_array = np.frombuffer(img_bytes, np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

            if image is None:
                return error("Invalid image data")

            image = add_margin(image, margin_ratio=0.05)

            face_app = request.app.state.face_app
            embedding = await run_in_executor(get_face_embedding, image, face_app)

            if embedding is None:
                return error("Face not detected in the image")
            embedding = [float(x) for x in embedding]

        client.execute(
            "INSERT INTO persons (sgb_person_id) VALUES",
            [(sgb_person_id,)]
        )
        person_id = client.execute(
            "SELECT id FROM persons WHERE sgb_person_id = %(sgb)s",
            {"sgb": sgb_person_id}
        )[0][0]
        if photo:
            img_path = f"images/persons/{sgb_person_id}/{person_id}.jpg"
            save_image(img_bytes, img_path)
        client.execute(
            """
            INSERT INTO person_documents
            (person_id, citizen, citizen_sgb, dtb, passport,
             passport_expired, sex, full_name, face_url, polygons)
            VALUES
            """,
            [{
              "person_id": person_id,
              "citizen": citizen,
              "citizen_sgb": citizen_sgb,
              "dtb": date_of_birth_dt,
              "passport": passport_number,
              "passport_expired": passport_expired_dt,
              "sex": sex,
              "full_name": full_name,
              "face_url": img_path,
              "polygons": embedding
            }]
        )

        client.execute(
            """
            INSERT INTO person_borders
            (border_id, person_id, reg_date, direction_country,
             direction_country_sgb, visa_type, visa_number,
             visa_organ, visa_date_from, visa_date_to, action)
            VALUES
            """,
            [(border_id, person_id, reg_date_dt,
              direction_country, direction_country_sgb,
              visa_type, visa_number, visa_organ,
              visa_date_from, visa_date_to, action)]
        )
        return success(
            "Person successfully registered",
            data={"person_id": str(person_id)}
        )
    except Exception as e:
        print(e)
        return error("Interval server error", 500)


@router.post("/update-sgb-id")
async def update_sgb_id(
    request: Request,
    old_sgb_person_id: int = Body(...),
    new_sgb_person_id: int = Body(...)
):
    try:
        person_result = client.execute(
            "SELECT id FROM persons WHERE sgb_person_id = %(old_sgb_person_id)s",
            {"old_sgb_person_id": old_sgb_person_id}
        )

        if not person_result:
            return JSONResponse(
                status_code=404,
                content={"message": "Bunday SGB person ID bo'yicha ma'lumot topilmadi"}
            )

        person_id = person_result[0][0]

        client.execute(
            "INSERT INTO persons (id, sgb_person_id) VALUES",
            [(person_id, new_sgb_person_id)]
        )

        return JSONResponse(
            status_code=200,
            content={"message": "SGB ID yangilandi"}
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": "Xatolik yuz berdi", "error": str(e)}
        )


@router.post("/update-passport-dtb")
async def update_passport_dtb(
    request: Request,
    sgb_person_id: int = Body(...),
    old_passport_number: str = Body(...),
    new_passport_number: str = Body(...),
    old_date_of_birth: str = Body(...),
    new_date_of_birth: str = Body(...)
):
    """Passport va tug'ilgan sanani yangilash (JSON formatida)"""
    try:
        old_date_of_birth_dt = datetime.strptime(old_date_of_birth, "%Y-%m-%d").date()
        new_date_of_birth_dt = datetime.strptime(new_date_of_birth, "%Y-%m-%d").date()

        person_documents = client.execute(
            """
            SELECT id, person_id, citizen, citizen_sgb, passport_expired,
                   sex, full_name, face_url, polygons
            FROM person_documents
            WHERE passport = %(old_passport_number)s
              AND dtb = %(old_date_of_birth)s
              AND person_id = (SELECT id FROM persons WHERE sgb_person_id = %(person_id)s)
            """,
            {
                "old_passport_number": old_passport_number,
                "old_date_of_birth": old_date_of_birth_dt,
                "person_id": sgb_person_id
            }
        )

        if not person_documents:
            return JSONResponse(
                status_code=404,
                content={"message": "Bunday passport va tug'ilgan sana bo'yicha ma'lumot topilmadi"}
            )
        person_document_id = person_documents[0][0]
        person_id = person_documents[0][1]
        citizen = person_documents[0][2]
        citizen_sgb = person_documents[0][3]
        passport_expired = person_documents[0][4]
        sex = person_documents[0][5]
        full_name = person_documents[0][6]
        face_url = person_documents[0][7]
        polygons = person_documents[0][8]

        client.execute(
            """
            INSERT INTO person_documents (id, person_id, citizen, citizen_sgb, dtb,
                                         passport, passport_expired, sex, full_name,
                                         face_url, polygons)
            VALUES
            """,
            [(person_document_id, person_id, citizen, citizen_sgb, new_date_of_birth_dt,
              new_passport_number, passport_expired, sex, full_name, face_url, polygons)]
        )

        return JSONResponse(
            status_code=200,
            content={"message": "Passport va tug'ilgan sana yangilandi"}
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": "Xatolik yuz berdi", "error": str(e)}
        )


@router.post("/update-person-border")
async def update_person_border(
    request: Request,
    sgb_person_id: int = Body(...),
    in_date: str = Body(...),
    out_date: str = Body(...),
    action: str = Body(...)
):
    """Person border ma'lumotlarini yangilash (JSON formatida)"""
    try:
        person_result = client.execute(
            "SELECT id FROM persons WHERE sgb_person_id = %(sgb_person_id)s",
            {"sgb_person_id": sgb_person_id}
        )

        if not person_result:
            return JSONResponse(
                status_code=404,
                content={"message": "Bunday SGB person ID bo'yicha ma'lumot topilmadi"}
            )

        person_id = person_result[0][0]

        in_date_dt = datetime.strptime(in_date, "%Y-%m-%d %H:%M:%S")
        out_date_dt = datetime.strptime(out_date, "%Y-%m-%d %H:%M:%S")

        person_borders = client.execute(
            """
            SELECT id, direction_country, direction_country_sgb
            FROM person_borders
            WHERE person_id = %(person_id)s AND reg_date = %(in_date)s
            """,
            {"person_id": person_id, "in_date": in_date_dt}
        )

        if not person_borders:
            return JSONResponse(
                status_code=404,
                content={"message": "Bunday person border bo'yicha ma'lumot topilmadi"}
            )

        person_border_id = person_borders[0][0]
        direction_country = person_borders[0][1]
        direction_country_sgb = person_borders[0][2]

        client.execute(
            """
            INSERT INTO person_borders (id, person_id, reg_date, direction_country,
                                       direction_country_sgb, action)
            VALUES
            """,
            [(person_border_id, person_id, out_date_dt, direction_country,
              direction_country_sgb, action)]
        )

        return JSONResponse(
            status_code=200,
            content={"message": "Person border yangilandi"}
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": "Xatolik yuz berdi", "error": str(e)}
        )


@router.get("/get-person/{sgb_person_id}")
async def get_person(sgb_person_id: int):
    """Person ma'lumotlarini olish"""
    try:
        person_result = client.execute(
            """
            SELECT p.id, p.sgb_person_id, pd.full_name, pd.passport,
                   pd.dtb, pd.passport_expired, pd.sex, pd.citizen,
                   pd.citizen_sgb, pd.face_url
            FROM persons p
            JOIN person_documents pd ON p.id = pd.person_id
            WHERE p.sgb_person_id = %(sgb_person_id)s
            """,
            {"sgb_person_id": sgb_person_id}
        )

        if not person_result:
            return JSONResponse(
                status_code=404,
                content={"message": "Person topilmadi"}
            )

        border_result = client.execute(
            """
            SELECT reg_date, direction_country, direction_country_sgb, action
            FROM person_borders
            WHERE person_id = %(person_id)s
            ORDER BY reg_date DESC
            """,
            {"person_id": person_result[0][0]}
        )

        person_data = {
            "person_id": str(person_result[0][0]),
            "sgb_person_id": person_result[0][1],
            "full_name": person_result[0][2],
            "passport": person_result[0][3],
            "date_of_birth": person_result[0][4].strftime("%Y-%m-%d") if person_result[0][4] else None,
            "passport_expired": person_result[0][5].strftime("%Y-%m-%d") if person_result[0][5] else None,
            "sex": person_result[0][6],
            "citizen": person_result[0][7],
            "citizen_sgb": person_result[0][8],
            "face_url": person_result[0][9],
            "borders": []
        }

        for border in border_result:
            person_data["borders"].append({
                "reg_date": border[0].strftime("%Y-%m-%d %H:%M:%S"),
                "direction_country": border[1],
                "direction_country_sgb": border[2],
                "action": border[3]
            })

        return JSONResponse(
            status_code=200,
            content=person_data
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": "Xatolik yuz berdi", "error": str(e)}
        )