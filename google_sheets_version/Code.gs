/**
 * GULYWOOD Casting Backend (Google Apps Script)
 * Установите этот код в Extensions -> Apps Script вашей таблицы.
 * Не забудьте создать папку на Google Drive для фото/видео и вписать её ID ниже.
 */

const FOLDER_ID = "ВСТАВЬТЕ_ID_ПАПКИ_GOOGLE_DRIVE_ЗДЕСЬ";

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName("Анкеты") || ss.insertSheet("Анкеты");
    
    // Если лист пустой, добавляем заголовки
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        "Дата", "ФИО", "Проект", "Роль", "Город", "Пол", "Возраст", 
        "Рост", "Вес", "Телефон", "Контакт", "Опыт", "Фото Ссылка", "Видео Ссылка"
      ]);
    }

    // Обработка файлов (Base64 -> Google Drive)
    let photoUrl = "";
    let videoUrl = "";

    if (data.photoBase64) {
      photoUrl = saveFile(data.photoBase64, data.photoName, "image/jpeg");
    }
    if (data.videoBase64) {
      videoUrl = saveFile(data.videoBase64, data.videoName, "video/mp4");
    }

    // Запись строки
    sheet.appendRow([
      new Date(),
      data.full_name,
      data.project_name,
      data.character_name,
      data.city,
      data.gender,
      data.age,
      data.height,
      data.weight,
      data.phone,
      data.contact,
      data.experience,
      photoUrl,
      videoUrl
    ]);

    return ContentService.createTextOutput(JSON.stringify({ status: "success", photoUrl, videoUrl }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("Анкеты");
  if (!sheet) return jsonResponse([]);
  
  const data = sheet.getDataRange().getValues();
  const headers = data[0];
  const rows = data.slice(1);
  
  const result = rows.map(row => {
    let obj = {};
    headers.forEach((header, i) => obj[header] = row[i]);
    return obj;
  });
  
  return jsonResponse(result);
}

function jsonResponse(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

function saveFile(base64, name, type) {
  const folder = DriveApp.getFolderById(FOLDER_ID);
  const decoded = Utilities.base64Decode(base64.split(",")[1]);
  const blob = Utilities.newBlob(decoded, type, name);
  const file = folder.createFile(blob);
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  return file.getUrl();
}
