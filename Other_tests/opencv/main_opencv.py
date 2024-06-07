import cv2
import numpy as np
import pyautogui
import easyocr
import time
import pyperclip
import keyboard
import pygame

# Инициализация микшера pygame
pygame.mixer.init()

# Флаг для включения/выключения копирования текста в буфер обмена
COPY_TO_CLIPBOARD = True

def capture_screen(region=(0, 0, 1920, 1080)):
    start_time = time.time()
    # Захват области экрана с помощью pyautogui
    screenshot = pyautogui.screenshot(region=region)
    # Преобразование изображения в формат, пригодный для обработки OpenCV
    img = np.array(screenshot)
    # OpenCV использует цветовой формат BGR, а pyautogui - RGB, поэтому конвертируем изображение
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    end_time = time.time()
    print(f"Screen Capturing: {end_time - start_time:.2f} sec")
    # Воспроизведение звука после снятия скриншота
    pygame.mixer.music.load('01.mp3')
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)
    return img

def convert_to_grayscale(image):
    # Преобразование изображения в оттенки серого
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return gray_image

def recognize_text(image):
    start_time = time.time()
    # Инициализация EasyOCR reader
    reader = easyocr.Reader(['en'])  # Укажите нужные языки
    # Распознавание текста на изображении
    result = reader.readtext(image)
    # Объединение результатов в строку
    text = "\n".join([item[1] for item in result])
    end_time = time.time()
    print(f"Text Recognition: {end_time - start_time:.2f} sec")
    return text

def save_screenshot(image, region, filename='screenshot.png'):
    # Рисование фиолетового прямоугольника на изображении
    x, y, w, h = region
    color = (255, 0, 255)  # Фиолетовый цвет в формате BGR
    thickness = 2
    cv2.rectangle(image, (x, y), (x + w, y + h), color, thickness)
    # Сохранение изображения
    cv2.imwrite(filename, image)
    print(f"Screenshot saved: {filename}")

def process_image():
    total_start_time = time.time()
    # Определение области захвата (вы можете изменить эти значения для настройки области)
    region = (0, 0, 1800, 880)  # Пример: захват области, которая начинается с (0, 0) и размером 1800x880
    # Захват экрана с указанной областью
    screen_image = capture_screen(region=region)
    # Преобразование изображения в оттенки серого
    gray_image = convert_to_grayscale(screen_image)
    # Распознавание текста на скриншоте
    recognized_text = recognize_text(gray_image)
    # Копирование распознанного текста в буфер обмена, если флаг установлен в True
    if COPY_TO_CLIPBOARD:
        pyperclip.copy(recognized_text)
        print("Recognized text copied to clipboard")
        # Воспроизведение звука после копирования текста в буфер обмена
        pygame.mixer.music.load('02.mp3')
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
    else:
        print("Copy to clipboard is disabled")
    # Сохранение скриншота с фиолетовым прямоугольником
    save_screenshot(screen_image, region)
    # Вывод распознанного текста в консоль
    print("Recognized Text:")
    print(recognized_text)
    total_end_time = time.time()
    print(f"\nTotal Time: {total_end_time - total_start_time:.2f} sec")

def main():
    print("Press 'shift' to start the process...")
    keyboard.add_hotkey('shift', process_image)
    keyboard.wait('esc')  # Программа будет работать до нажатия 'Esc'

if __name__ == "__main__":
    main()
