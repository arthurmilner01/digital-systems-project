#include <WiFi.h> //WiFi
#include <PubSubClient.h> //MQTT
#include <MFRC522.h> //RFID
#include <SPI.h> //RFID
#include <Ultrasonic.h> //Ultrasonic sensors
#include <HX711.h> //Scale
#include <Wire.h> //I2C
#include <LiquidCrystal_I2C.h> //LCD
#include <ArduinoJson.h> //For decoding MQTT response

//Ultrasonic sensor
#define TRIG_PIN 25
#define ECHO_PIN 26
//LED
#define LED_PIN 2
//RFID
#define SS_PIN 5
#define SCK_PIN 18
#define MOSI_PIN 23
#define MISO_PIN 19
#define RST_PIN 4
//Scale
#define SCALE_SCK 16
#define SCALE_DT 17
//I2C (for LCD screen)
#define SDA_PIN 21
#define SCL_PIN 22
//Button
#define BUTTON_PIN 15

//WiFi details
const char* ssid = "******";
const char* password = "******";

//MQTT broker details
const char* mqtt_server = "192.168.1.100"; //IP of Raspberry Pi/MQTT server
const int mqtt_port = 1883; //MQTT port
const char* mqtt_user = "******"; //MQTT username
const char* mqtt_password = "******"; //MQTT password

//MQTT topics
const char* topic_customer = "shop/customer"; //Topic for dispense details to add dispense to customer basket (rfid UID, product name, weight, and cost)
const char* topic_business_capacity = "shop/business/capacity"; //Topic for product capacity details (product name and capacity %)
const char* topic_business_dispense = "shop/business/dispense"; //Topic for product dispense details (product name, weight, and cost)
const char* topic_dispenser_details = "dispenser/details"; //Topic to request dispenser details (dispenser ID)
const char* topic_dispenser_response = "dispenser/response/2"; //Subscribe topic listening on dispenser ID of 2 (product name and cost)
const char* topic_verify_rfid = "dispenser/verify"; //Topic to validate scanned RFID UID (dispenser ID and rfid UID)
const char* topic_verify_response = "dispenser/verify/2"; //Subscribe topic listening on dispenser ID of 2 (rfid valid (true/false))

String PRODUCT_NAME = ""; //To be populated by MQTT response
float COST_PER_GRAM = 0.0; //To be populated by MQTT response
bool rfidValid = false;

MFRC522 rfid(SS_PIN, RST_PIN); //RFID
Ultrasonic ultrasonic(TRIG_PIN, ECHO_PIN); //Ultrasonic sensor
HX711 scale; //Scale
LiquidCrystal_I2C lcd(0x27, 16, 2); //LCD

WiFiClient espClient; //Wifi setup
PubSubClient client(espClient); //MQTT connection/setup

const float MAX_DISTANCE = 16.00;
const float LOW_CAPACITY = 12.00;
const float DISPENSE_DELAY = 15000; //Delay between dispenses


//Connects ESP32 to WiFi
void setup_wifi()
{
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  lcd.clear();

  //For showing the loading
  int dotPosition = 0;
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    lcd.setCursor(0, 0);
    lcd.print("Connecting Wi-Fi");
    lcd.setCursor(dotPosition,1);
    lcd.print(".");
    //Next dot will print to the right
    dotPosition++;
    Serial.println(".");
  }
  Serial.println();
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

//Function to reconnect to MQTT broker
void reconnect_MQTT() 
{
  //Loops until reconnected to MQTT broker
  while (!client.connected())
  {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Reaching Checkout");
    Serial.println("Attempting MQTT connection...");
    int dotPosition = 0;
    if (client.connect("ESP32Client", mqtt_user, mqtt_password))
    {
      Serial.println("connected");
      //Subscribing to rfid validation topic
      client.subscribe(topic_verify_response);
      //Subscribing to response topic
      client.subscribe(topic_dispenser_response);
    }
    else 
    {
      lcd.setCursor(dotPosition,1);
      lcd.print(".");
      dotPosition++;
      Serial.println("Failed, Reason Code=");
      Serial.println(client.state());
      Serial.println(" trying again in 5 seconds...");
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
        lcd.clear();
        lcd.setCursor(0,0);
        lcd.print("Error getting");
        lcd.setCursor(0,1);
        lcd.print("details: Reboot.");
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

    Serial.println("Received message: " + JSONMessage);

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
         Serial.println("isValidRFID: "+ String(isValidRFID));

         if(isValidRFID)
         {
            rfidValid = true;
         }
         else
         {
            rfidValid = false;
         }
      }
    }
    else //If mqtt error
    {

      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print("Error:");
      lcd.setCursor(0,1);
      lcd.print("Validation fail.");
      delay(1000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  //LCD setup
  lcd.init();
  lcd.backlight(); 
  lcd.setCursor(0, 0);
  lcd.print("LCD ready");
  lcd.setCursor(0, 1);
  lcd.print("Starting system...");
  delay(3000);

  //Wi-fi and MQTT
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  reconnect_MQTT();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Connected!");
  delay(1000);

  //Subscribing to rfid validation topic
  client.subscribe(topic_verify_response);

  //Subscribing to response topic
  client.subscribe(topic_dispenser_response);

  //Sending request for dispenser product details on ID 2
  String detailsPayload = "{ \"dispenser_id\": 2 }";
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
      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print("Couldn't get");
      lcd.setCursor(0, 1);
      lcd.print("details: Reboot.");
      delay(1000);
    }
    else
    {
      break;
    }
  }

  Serial.println(PRODUCT_NAME);
  Serial.println(COST_PER_GRAM);

  //Button
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  //Ultrasonic setup
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  //LED setup
  pinMode(LED_PIN, OUTPUT);

  //RFID setup
  SPI.begin();
  rfid.PCD_Init();
  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print("Scanner ready...");
  delay(1000);

  //Scale setup
  scale.begin(SCALE_DT, SCALE_SCK);

  //Zero scale
  scale.tare();
  delay(1000);
  //Calibrate the scale on system start up
  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print("Place 500g...");
  lcd.setCursor(0,1);
  lcd.print("Press button...");

  //Waiting for button press
  while (digitalRead(BUTTON_PIN) == HIGH) {
    delay(50);
  }

  //Uses known weight to calculate appropriate calibration factor
  if(scale.is_ready())
  {
    float scaleValue = scale.get_value(50); //Gets scales average reading over 10 readings

    //Calculating calibration factor based on the error between scale reading and known weight
    float knownWeight = 500.0; //Weight of calibration weight
    float calibrationFactor = scaleValue / knownWeight;
    scale.set_scale(calibrationFactor);

    //Display calibration factor
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Calibration Done!");
    lcd.setCursor(0,1);
    lcd.print("Remove weight...");
    Serial.println(String(calibrationFactor, 2));
    delay(10000);
  } 
  else
  {
    //Show error message if scale not ready
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Error with scale...");
    lcd.setCursor(0,1);
    lcd.print("Restart system.");
    while (true); //Stop program if scale not ready
  }
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

  //Read capacity
  distance = ultrasonic.read();
  //Convert to % by using max capacity
  percentFull = ((MAX_DISTANCE-distance) / MAX_DISTANCE) * 100;

  Serial.print("Distance: ");
  Serial.print(distance);
  Serial.println(" cm");

  //If reading over max distance assume empty capacity
  if(distance > MAX_DISTANCE)
  {
    percentFull = 0;
    Serial.print("Capacity: ");
    Serial.print(percentFull);
    Serial.println("%");
  }
  else
  {
    Serial.print("Capacity: ");
    Serial.print(percentFull);
    Serial.println("%");
  }

  //LED indicator if capacity is low
  if(distance > LOW_CAPACITY)
  {
    digitalWrite(LED_PIN, HIGH);
  }
  else
  {
    digitalWrite(LED_PIN, LOW);
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
  else //If error sending data message is displayed
  {
    Serial.println("Failed to send capacity.");
  }

  unsigned long decimalUID = 0; //To store the RFID ID

  //Loops until an rfid tag is scanned
  while (true)
  {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Place container");
    lcd.setCursor(0,1);
    lcd.print("& scan tag...");

    if(rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial())
    {
      decimalUID = 0;
      for (byte i = 0; i < (rfid.uid.size); i++)
      {
          decimalUID = decimalUID * 256 + rfid.uid.uidByte[i];
      }
      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();

      if (!client.connected()) {
        reconnect_MQTT();
      }
      client.loop();

      //Set rfid valid to false before beginning validation
      rfidValid = false;

      //Sending rfid validation request with dispenser id
      String rfidValidPayload = "{ \"rfid_uid\": " + String(decimalUID) + ", \"dispenser_id\": 2 }";
      if(client.publish(topic_verify_rfid, rfidValidPayload.c_str())) 
      {
        Serial.println("RFID verification message sent successfully");
      } 
      else 
      {
        Serial.println("Failed to send RFID verification message");
      }
      //Wait for MQTT response, times out after 10 seconds and presents error
      unsigned long startTime = millis();
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Verifying");
      lcd.setCursor(0,1);
      lcd.print("tag...");
      //While rfid is not valid or not yet timed out listen for response
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
        lcd.clear();
        lcd.setCursor(0,0);
        lcd.print("Tag valid!");
        lcd.setCursor(0,1);
        lcd.print("Starting dispense...");
        delay(2500);
        break;
      }
      else //Wait for another tag
      {
        lcd.clear();
        lcd.setCursor(0, 0);
        lcd.print("Invalid");
        lcd.setCursor(0,1);
        lcd.print("tag...");
        delay(2500);
      }
    }
  
    delay(100);
  }

  //Set rfid valid to false again
  rfidValid = false;

  float amountDispensed = 0;
  float costDispensed = 0;
  //To only display the highest previous amount/cost
  float currentWeight = 0;

  //Zero scale so calculating weight of dispensed product
  scale.tare();

  while(true)
  {
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

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Amount:");
    lcd.print(String(amountDispensed)+"g");
    lcd.setCursor(0,1);
    lcd.print("Cost:");
    lcd.print(String(costDispensed));

    if(digitalRead(BUTTON_PIN) == LOW) //When button pressed stop dispensing
    {
      delay(50);
      break;
    }

    delay(100);
  }

  //If amount dispensed or cost are incorrectly calculated
  //Max weight of 5kg max cost of £200
  if(amountDispensed < 0.01 || amountDispensed > 5000 || costDispensed < 0.01 || costDispensed > 200)
  {
    //Display error to customer, employee can add dispense at checkout
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print("Error: Get");
    lcd.setCursor(0,1);
    lcd.print("help at checkout");
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

    //Trys to reconnect if connection drops
    if (!client.connected())
    {
      reconnect_MQTT();
    }
    client.loop();

    //Publishing to MQTT customer topic
    if(client.publish(topic_customer, payload.c_str())) 
    {
      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print("Dispense sent");
      lcd.setCursor(0,1);
      lcd.print("Cost: "+ String(costDispensed, 2));

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
      //Display success message
      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print("Error: Get");
      lcd.setCursor(0,1);
      lcd.print("help at checkout");
      
      delay(5000);
    }
  }

  //Display dispense complete message
  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print("Remove container");
  lcd.setCursor(0,1);
  lcd.print("Dispense done.");
  //Delay to allow removal of container
  delay(DISPENSE_DELAY);
  //Zero scale again
  scale.tare();
}
