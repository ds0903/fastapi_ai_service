// Google Apps Script для отправки webhook при изменениях в таблице
// Вставьте этот код в редактор Apps Script

const WEBHOOK_URL = 'http://167.86.106.99:8013/webhook/sheets-update';
const SHEET_ID = '1chSraYNxqbnzMqExnTW5eZDcOhJgLxHNpf9wMJHeX-s';

function onEdit(e) {
  try {
    // Получаем информацию об изменении
    const range = e.range;
    const sheet = range.getSheet();
    const sheetName = sheet.getName();
    
    // Игнорируем изменения в служебных листах
    if (sheetName.startsWith('_') || sheetName === 'Настройки') {
      return;
    }
    
    // Собираем данные для отправки
    const data = {
      sheetName: sheetName,
      row: range.getRow(),
      column: range.getColumn(),
      columnLetter: columnToLetter(range.getColumn()),
      value: e.value || '',
      oldValue: e.oldValue || '',
      operation: e.value ? 'update' : 'delete',
      timestamp: new Date().toISOString(),
      user: e.user.email
    };
    
    // Отправляем webhook
    sendWebhook(data);
    
  } catch (error) {
    console.error('Error in onEdit:', error);
  }
}

function sendWebhook(data) {
  try {
    const options = {
      'method': 'post',
      'contentType': 'application/json',
      'payload': JSON.stringify(data),
      'muteHttpExceptions': true
    };
    
    const response = UrlFetchApp.fetch(WEBHOOK_URL, options);
    const responseCode = response.getResponseCode();
    
    if (responseCode !== 200) {
      console.error('Webhook failed with code:', responseCode);
      console.error('Response:', response.getContentText());
    } else {
      console.log('Webhook sent successfully for', data.sheetName, 'row', data.row);
    }
    
  } catch (error) {
    console.error('Error sending webhook:', error);
  }
}

function columnToLetter(column) {
  let letter = '';
  while (column > 0) {
    const remainder = (column - 1) % 26;
    letter = String.fromCharCode(65 + remainder) + letter;
    column = Math.floor((column - 1) / 26);
  }
  return letter;
}

// Функция для тестирования webhook
function testWebhook() {
  const testData = {
    sheetName: 'Мастер',
    row: 10,
    column: 4,
    columnLetter: 'D',
    value: 'Тест из Apps Script',
    oldValue: '',
    operation: 'update',
    timestamp: new Date().toISOString(),
    user: 'test@gmail.com'
  };
  
  sendWebhook(testData);
  console.log('Test webhook sent');
}

// Функция для установки триггера (запустить один раз)
function installTrigger() {
  // Удаляем старые триггеры
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => ScriptApp.deleteTrigger(trigger));
  
  // Создаем новый триггер на изменение
  ScriptApp.newTrigger('onEdit')
    .forSpreadsheet(SHEET_ID)
    .onEdit()
    .create();
    
  console.log('Trigger installed successfully');
}
