#include <WiFi.h>
#include <PubSubClient.h> //MQTT
#include <Wire.h>
#include <Adafruit_GFX.h> //OLED
#include <Adafruit_SSD1306.h> //OLED
#include <SPI.h>
#include <MFRC522.h> //RFID
#include <HX711.h> //Scale
#include <Ultrasonic.h> //Ultrasonic sensor
#include <Math.h> //For height calculation
#include <ArduinoJson.h> //For decoding MQTT response
#include <Adafruit_VL53L1X.h> //ToF sensor

//OLED display
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
//OLED
#define SDA_PIN 21
#define SCL_PIN 22
//RFID RC522
#define RST_PIN 27
#define SS_PIN 5
//Button
#define BUTTON_PIN 25
//Scale
#define SCALE_DT 4
#define SCALE_SCK 16
//Ultrasonic Sensor (Measures capacity)
#define TRIG_PIN 12
#define ECHO_PIN 13
//Relay
#define RELAY_PIN 26

//WiFi details
const char* ssid = "******";
const char* password = "******";

//MQTT broker details
const char* mqtt_server = "192.168.1.100"; //IP of Raspberry Pi/MQTT server
const int mqtt_port = 1883; //MQTT port
const char* mqtt_user = "******"; //MQTT username
const char* mqtt_password = "******"; //MQTT password

//MQTT topics
const char* topic_customer = "shop/customer"; //Topic for customer basket details
const char* topic_business_capacity = "shop/business/capacity"; //Topic for product capacity details
const char* topic_business_dispense = "shop/business/dispense"; //Topic for product dispense details
const char* topic_dispenser_details = "dispenser/details"; //Topic to request dispenser details
const char* topic_dispenser_response = "dispenser/response/1"; //Dispenser ID of 1
const char* topic_verify_rfid = "dispenser/verify"; //Topic to validate scanned RFID UID
const char* topic_verify_response = "dispenser/verify/1"; //Dispenser ID of 1

String PRODUCT_NAME = ""; //To be populated by MQTT response
float COST_PER_GRAM = 0.0; //To be populated by MQTT response
bool rfidValid = false; //RFID MQTT validation (set true if valid)

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1); //OLED
MFRC522 rfid(SS_PIN, RST_PIN); //RFID
HX711 scale; //Scale
Adafruit_VL53L1X tof = Adafruit_VL53L1X(); //ToF sensor for detecting container on scale
Ultrasonic ultrasonic(TRIG_PIN, ECHO_PIN); //Ultrasonic (Recording the capacity level)


WiFiClient espClient; //Wifi setup
PubSubClient client(espClient); //MQTT connection/setup

const float MAX_DISTANCE = 27.00; //For calculating capacity % (Height from ultrasonic to bottom of container)
const float DISPENSE_DELAY = 15000; //Delay between dispenses
const float CONTAINER_DETECTION = 400; //Distance to detect whether or not a container is on scale in mm

//Connects ESP32 to WiFi
void setup_wifi()
{
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  int dotPosition = 0;
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Connecting Wi-Fi:");
  display.display();
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    display.setCursor(dotPosition, 3);
    display.print(".");
    display.display();
    //Next dot will print to the right
    dotPosition++;
  }
  Serial.println();
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

//Function to reconnect to MQTT broker
void reconnect_MQTT()
{
  int dotPosition = 0;
  Serial.println("Attempting MQTT connection...");
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Reaching checkout...");
  display.display();
  //Loops until reconnected to MQTT broker
  while (!client.connected()) {
    if (client.connect("ESP32Client", mqtt_user, mqtt_password))
    {
      Serial.println("connected");
      //Re-subscribing to rfid validation topic
      client.subscribe(topic_verify_response);
      //Re-subscribing to response topic
      client.subscribe(topic_dispenser_response);
    } 
    else 
    {
      
      display.setCursor(0, 3);
      display.print("Reason Code:");
      display.print(client.state());
      display.setCursor(dotPosition, 4);
      display.print(".");
      display.display();
      dotPosition++;
      delay(5000);
    }
  }
}

//Callback function for receieving MQTT messages, adapted from https://randomnerdtutorials.com/esp32-mqtt-publish-subscribe-arduino-ide/
void callback(char* topic, byte* message, unsigned int length) 
{
  //If topic matches dispenser ID
  if(String(topic) == String(topic_dispenser_response))
  {
    //Get the message
    String JSONMessage;
    for (unsigned int i = 0; i < length; i++)
    {
      JSONMessage += (char)message[i];
    }
    //Using ArduinoJson library to parse the JSON string message
    //200 represents the bytes set aside for parsing
    StaticJsonDocument<200> doc;
    //Checks if the message is correctly deserialised
    DeserializationError error = deserializeJson(doc, JSONMessage);

    if (!error) //If no error
    {
      //Set product_name and cost_per_gram from parsed JSON to the ESP32 variables
      if (doc.containsKey("product_name") && doc.containsKey("cost_per_gram")) 
      {
        PRODUCT_NAME = doc["product_name"].as<String>();
        COST_PER_GRAM = doc["cost_per_gram"].as<float>();
        Serial.println("Received updated product details:");
        Serial.print("Name: ");
        Serial.println(PRODUCT_NAME);
        Serial.print("Cost per gram: ");
        Serial.println(COST_PER_GRAM);
      }
    }
    else
    {
      while(true)
      {
        display.clearDisplay();
        display.setCursor(0,0);
        display.println("Error getting product details...");
        display.setCursor(0,1);
        display.println("Please reboot dispenser...");
        delay(1000);
      }
    }
  }

  //If topic matches dispenser ID
  if(String(topic) == String(topic_verify_response))
  {
    //Get the message
    String JSONMessage;
    for (unsigned int i = 0; i < length; i++)
    {
      JSONMessage += (char)message[i];
    }

    //Using ArduinoJson library to parse the JSON string message
    //200 represents the bytes set aside for parsing
    StaticJsonDocument<200> doc;
    //Checks if the message is correctly deserialised
    DeserializationError error = deserializeJson(doc, JSONMessage);

    if (!error) //If no error
    {
      //If reponse is valid rfid set valid rfid to true
      if (doc.containsKey("rfid_valid"))
      {
        //Extract the value
         bool isValidRFID = doc["rfid_valid"].as<bool>();

         if(isValidRFID)
         {
            rfidValid = true;
            display.clearDisplay();
            display.setCursor(0,0);
            display.println("Valid tag...");
            display.display();
            delay(1000);
         }
         else
         {
            rfidValid = false;
            display.clearDisplay();
            display.setCursor(0,0);
            display.println("Invalid tag...");
            display.display();
            delay(1000);
         }
      }
    }
    else //If mqtt error
    {
      display.clearDisplay();
      display.setCursor(0,0);
      display.println("Error validating tag...");
      delay(1000);
    }
  }
}

//Dispensing function
//Passing by reference so value can be altered within function
void Dispense(float &amountDispensed, float &costDispensed)
{
  //To only display the highest previous amount/cost
  float currentWeight = 0;

  digitalWrite(RELAY_PIN, HIGH); //Turn on pump

  while(true)
  {
    //Read ToF value
    int containerDistance = tof.distance();
    tof.clearInterrupt();
    //If container is detected as removed from scale
    if(containerDistance > CONTAINER_DETECTION)
    {
      digitalWrite(RELAY_PIN, LOW); //Turn off pump
      display.println("Container no longer detected...");
      display.display();
      delay(2000);
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("Amount Dispensed:");
      display.println(String(amountDispensed)+"g");
      display.println("Total Cost:");
      display.println(String(costDispensed));
      display.display();
      delay(2000);
      break;
    }
    
    if(scale.is_ready())
    {
      currentWeight = scale.get_units(10);
    }

    if(currentWeight < 0)
    {
      currentWeight = 0;
    }

    if(currentWeight > amountDispensed)
    {
      amountDispensed = currentWeight; //Weight
      costDispensed = (amountDispensed * COST_PER_GRAM) / 100; //Cost
    }

    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Amount Dispensed:");
    display.println(String(amountDispensed)+"g");
    display.println("Total Cost:");
    display.println(String(costDispensed));
    display.println("To stop dispensing press button...");
    display.display();

    if(digitalRead(BUTTON_PIN) == LOW) //When button pressed stop dispensing
    {
      digitalWrite(RELAY_PIN, LOW); //Turn off pump
      delay(2000);
      break;
    }

    delay(100);
  }
}

void setup() 
{
  Serial.begin(115200);
  
  //I2C bus init
  Wire.begin(SDA_PIN, SCL_PIN);
  //Test OLED
  if (!display.begin(SSD1306_BLACK, 0x3C)) 
  { //0x3C is OLED I2C address
    Serial.println("Failed to initialize OLED!");
    while (true);
  }
  display.display();
  delay(2000);

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0,0);
  display.println("System Starting...");
  display.display();
  delay(3000);

  //Wi-fi and MQTT
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  reconnect_MQTT();
  display.clearDisplay();
  display.setCursor(0,0);
  display.println("Connected to wi-fi and checkout...");
  delay(2000);

  //Subscribing to rfid validation topic
  client.subscribe(topic_verify_response);
  //Subscribing to response topic
  client.subscribe(topic_dispenser_response);
  //Sending request for dispenser product details on ID 1
  String detailsPayload = "{ \"dispenser_id\": 1 }";
  client.publish(topic_dispenser_details, detailsPayload.c_str());
  //Wait for MQTT response, times out after 10 seconds and presents error
  unsigned long startTime = millis();
  //Whilst PRODUCT_NAME still not set
  while (PRODUCT_NAME == "" && (millis() - startTime < 10000))
  {
    if (!client.connected())
    {
      reconnect_MQTT();
    }
    client.loop();
    delay(100);
  }

  //Halt if failed to grab details
  while(true)
  {
    if(PRODUCT_NAME == "" || COST_PER_GRAM == 0.0)
    {
      display.clearDisplay();
      display.setCursor(0,0);
      display.println("Couldn't get product details, please reboot...");
      display.display();
      delay(1000);
    }
    else
    {
      display.clearDisplay();
      display.setCursor(0,0);
      display.print("Product: ");
      display.println(PRODUCT_NAME);
      display.print("Cost Per Gram: ");
      display.println(COST_PER_GRAM);
      display.display();
      delay(3000);
      break;
    }
  }

  //ToF sensor
  if (!tof.begin(0x29, &Wire)) 
  {
      display.clearDisplay();
      display.setCursor(0,0);
      display.println("Distance sensor error please reboot...");
      display.display();
      delay(1000);
      while (true);
  }
  tof.startRanging();

  display.clearDisplay();
  display.setCursor(0,0);
  display.println("ToF sensor ready.");
  display.display();
  delay(1000);

  //Button
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  display.println("Button ready.");
  display.display();
  delay(1000);

  //Relay
  pinMode(RELAY_PIN, OUTPUT);
  display.println("Relay ready.");
  display.display();
  delay(1000);

  //SPI and RFID setup
  SPI.begin();
  rfid.PCD_Init();
  display.println("RFID Ready.");
  display.display();
  delay(1000);

  //Scale setup
  scale.begin(SCALE_DT, SCALE_SCK);
  //Zero scale
  scale.tare();
  delay(1000);

  //Calibrate the scale on system start up
  display.clearDisplay();
  display.setCursor(0,0);
  display.println("Scale calibration needed!");
  display.println("Place 500g of weight on scale");
  display.println("and press button...");
  display.display();

  //Waiting for button press
  while (digitalRead(BUTTON_PIN) == HIGH) {
    delay(50);
  }

  //Uses known weight to calculate appropriate calibration factor
  if(scale.is_ready())
  {
    float scaleValue = scale.get_value(50); //Gets scales average reading over 50 readings

    //Calculating calibration factor based on the error between scale reading and known weight
    float knownWeight = 500.0; //Weight of calibration weight
    float calibrationFactor = scaleValue / knownWeight;
    scale.set_scale(calibrationFactor);

    //Display calibration factor
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Calibration Done!");
    display.print("Calibration Factor: ");
    display.println(String(calibrationFactor, 2));
    display.display();
    delay(1000);
  } 
  else
  {
    //Show error message if scale not ready
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("Error occured, scale is not ready.");
    display.println("Restart system and try again.");
    display.display();
    while (true); //Stop program if scale not ready
  }

  //Print scale ready if calibration successful
  display.println("Scale Ready! Please remove the calibration weight so the scale can reset.");
  display.display();
  delay(8000); //Delay to give time for removal of calibration weight
  scale.tare(); //Zero scale with new calibration factor
}

void loop()
{
  //Trys to reconnect if connection drops
  if (!client.connected())
  {
    reconnect_MQTT();
  }
  client.loop();

  float distance;
  float percentFull;

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Sending capacity data please wait...");
  display.display();

  //Read capacity
  distance = ultrasonic.read();
  //Convert to % by using max capacity
  percentFull = ((MAX_DISTANCE - distance) / MAX_DISTANCE) * 100;

   //If reading over max distance assume empty capacity
  if(distance > MAX_DISTANCE)
  {
    percentFull = 0;
  }

  //Reconnect to MQTT if connection drops
  if (!client.connected())
  {
    reconnect_MQTT();
  }
  client.loop();

  //Business capacity JSON payload
  String businessCapacityPayload = "{";
  businessCapacityPayload += "\"name\":\"" + PRODUCT_NAME + "\",";
  businessCapacityPayload += "\"capacity\":" + String(percentFull, 2);
  businessCapacityPayload += "}";

  //Publishing to MQTT under business capacity topic
  if(client.publish(topic_business_capacity, businessCapacityPayload.c_str())) 
  {
    Serial.println("Capacity successfully sent to dashboard.");
  } 
  else //If error sending data
  {
    Serial.println("Failed to send capacity.");
  }

  float amountDispensed = 0; //Tracks weight of dispense
  float costDispensed = 0; //Tracks cost of dispense
  unsigned long decimalUID = 0; //To store the RFID ID
  bool detectedContainer = false; //Track if container is on scale

  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Place container and scan a tag...");
  display.display();

  //Loops until an rfid tag is scanned or container is removed
  while (true) {
    if(rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial())
    {

      decimalUID = 0;
      for (byte i = 0; i < (rfid.uid.size); i++)
      {
          decimalUID = decimalUID * 256 + rfid.uid.uidByte[i];
      }
    
      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();

      //After tag is read check container is on scale
      while(!detectedContainer)
      {
        //Read ToF value
        if (tof.dataReady()) 
        {
          int tofDist = tof.distance();
          tof.clearInterrupt();
          //If container is detected as on the scale
          if(tofDist < CONTAINER_DETECTION)
          {
            display.println("Container detected...");
            display.display();
            delay(1000);
            detectedContainer = true;
          }
          display.clearDisplay();
          display.setCursor(0, 0);
          display.println("Checking for container...");
          display.println("Distance:");
          display.println(tofDist);
          display.display();
        }

        delay(100);
      }

      if (!client.connected()) 
      {
        reconnect_MQTT();
      }
      client.loop();

      //Set rfid valid to false before beginning validation
      rfidValid = false;

      //Sending rfid validation request with dispenser id
      String rfidValidPayload = "{ \"rfid_uid\": " + String(decimalUID) + ", \"dispenser_id\": 1 }";
      if(client.publish(topic_verify_rfid, rfidValidPayload.c_str())) 
      {
        Serial.println("RFID verification message sent successfully");
      } 
      else 
      {
        Serial.println("Failed to send RFID verification message");
      }

      //Wait for MQTT response, times out after 10 seconds and presents error
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("Verifying tag...");
      display.display();
      //While rfid is not valid or not yet timed out listen for response
      unsigned long startTime = millis();
      while (rfidValid==false && (millis() - startTime < 10000))
      {
        if (!client.connected()) 
        {
          reconnect_MQTT();
        }
        client.loop();
        delay(200);
      }

      //Break out while loop if rfid valid
      if(rfidValid)
      {
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("Tag validated!");
        display.display();
        delay(2500);
        break;
      }
      else //Display error then wait for another tag
      {
        display.clearDisplay();
        display.setCursor(0, 0);
        display.println("Error validating or an invalid tag was scanned...");
        display.display();
        delay(2500);
      }
    }
    delay(100);
  }

  //Set rfid valid to false again
  rfidValid = false;

  
  //Display RFID UID to customer
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Dispensing to tag ID:");
  display.println(String(decimalUID));
  display.display();
  delay(3000);

  if (scale.is_ready()) {
    scale.tare(); //Resetting scale so scale will read amount dispensed
  }
 
  Dispense(amountDispensed, costDispensed);

  //If amount dispensed or cost are incorrectly calculated
  //Max weight of 5kg max cost of £200
  if(amountDispensed < 0.01 || amountDispensed > 5000 || costDispensed < 0.01 || costDispensed > 200)
  {
    //Display error to customer, employee can add dispense at checkout
    display.clearDisplay();
    display.setCursor(0,0);
    display.println("Unexpected dispense readings, please inform staff at checkout.");
    display.display();
    delay(5000);
  }
  else
  {
    //Details which will send to MQTT
    //JSON string payload for MQTT of dispense details
    String payload = "{";
    //Sending as number
    payload += "\"rfid_uid\": " + String(decimalUID);
    //Sending as string
    payload += ",\"name\": \"" + PRODUCT_NAME + "\"";
    //Sending as number
    payload += ",\"weight\": " + String(amountDispensed, 2);
    //Sending as number
    payload += ",\"cost\": " + String(costDispensed, 2);
    payload += "}";

    //Reconnect to MQTT if connection drops
    if (!client.connected())
    {
      reconnect_MQTT();
    }
    client.loop();

    //Publishing to MQTT
    if(client.publish(topic_customer, payload.c_str())) 
    {
      display.clearDisplay();
      display.setCursor(0,0);
      display.println("Dispense successfully sent to checkout.");
      display.print("Amount: ");
      display.print(amountDispensed);
      display.println("g");
      display.print("Cost: ");
      display.println(costDispensed);
      display.display();
      
      //Trys to reconnect MQTT if connection drops
      if (!client.connected())
      {
        reconnect_MQTT();
      }
      client.loop();

      //Details which will send to MQTT
      //JSON string payload for MQTT of dispense details
      String businessDispensePayload = "{";
      //Sending as string
      businessDispensePayload += "\"name\": \"" + PRODUCT_NAME + "\"";
      //Sending as number
      businessDispensePayload += ",\"weight\": " + String(amountDispensed, 2);
      //Sending as number
      businessDispensePayload += ",\"cost\": " + String(costDispensed, 2);
      businessDispensePayload += "}";

      //Publishing to MQTT under business dispense topic
      if(client.publish(topic_business_dispense, businessDispensePayload.c_str())) 
      {
        Serial.println("Dispense successfully sent to dashboard.");
      } 
      else //If error sending data message is displayed
      {
        Serial.println("Failed to send dispense.");
      }

      delay(5000);
    } 
    else //If error sending data message is displayed
    {
      display.clearDisplay();
      display.setCursor(0,0);
      display.println("Failed to complete dispense, please inform staff at checkout.");
      display.display();

      delay(5000);
    }
  }
  
  //Delay between dispenses to allow customer to remove their container
  display.clearDisplay();
  display.setCursor(0,0);
  display.println("Preparing for next dispense, please remove your container...");
  display.display();
  delay(DISPENSE_DELAY);
}