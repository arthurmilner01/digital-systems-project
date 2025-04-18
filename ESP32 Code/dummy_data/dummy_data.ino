#include <WiFi.h>
#include <PubSubClient.h> //MQTT

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

WiFiClient espClient; //Wifi setup
PubSubClient client(espClient); //MQTT connection/setup

//Delay between publishing dummy data
const float DISPENSE_DELAY = 100000;
//Array of product names to randomly choose from
const char* PRODUCT_NAMES[] = {"Peanuts", "Cereal", "Olive Oil", "Chickpeas", "Green Peas", "Lentils", "Penne Pasta", "Washing Powder", "Sesame Oil", "Cornflakes"};
//Number of items in array
//sizeof(PRODUCT_NAMES) returns the number of bytes (one word should be 4 bytes)
//then sizeof(PRODUCT_NAMES[0]) will get the number of bytes in one word which will be the same for all words
//so sizeof(PRODUCT_NAMES) / sizeof(PRODUCT_NAMES[0]) will give the number of words in the array
const int PRODUCT_COUNT = sizeof(PRODUCT_NAMES) / sizeof(PRODUCT_NAMES[0]);
//Delay between sending dummy data
const unsigned long PUBLISH_DELAY = 100000;

//Connects ESP32 to WiFi
void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.println(".");
  }
  
  Serial.println();
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

//Function to reconnect to MQTT broker
void reconnect_MQTT() {
  //Loops until reconnected to MQTT broker
  while (!client.connected()) {
    Serial.println("Attempting MQTT connection...");
    if (client.connect("ESP32Client", mqtt_user, mqtt_password)) {
      Serial.println("connected");
    } else {
      Serial.println("failed, rc=");
      Serial.println(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}


void setup()
{
  Serial.begin(115200);
  //Wi-fi and MQTT
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
}

void loop() 
{
  //Gets random index to select product name from
  int productNameIndex = esp_random() % PRODUCT_COUNT;
  String productName = PRODUCT_NAMES[productNameIndex];
  //Random value between 0-100 for capacity % full
  float percentFull = esp_random() % 101;
  //Random value for amount dispensed (between 0.01 and 20.00)
  float amountDispensed = ((esp_random() % 2000) + 1) / 100;
  //Random value for cost dispensed (between 0.01 and 20.00)
  float costDispensed = ((esp_random() % 2000) + 1) / 100;

  //Details which will send to MQTT
  //JSON string payload for MQTT of capacity details
  //Random product name and capacity between 0-100 sent
  String businessCapacityPayload = "{";
  businessCapacityPayload += "\"name\":\"" + productName + "\",";
  businessCapacityPayload += "\"capacity\":" + String(percentFull, 2);
  businessCapacityPayload += "}";

  //JSON string payload for MQTT of dispense details
  //Random product name, amount, and cost
  String businessDispensePayload = "{";
  //Sending as string
  businessDispensePayload += "\"name\": \"" + productName + "\"";
  //Sending as number
  businessDispensePayload += ",\"weight\": " + String(amountDispensed, 2);
  //Sending as number
  businessDispensePayload += ",\"cost\": " + String(costDispensed, 2);
  businessDispensePayload += "}";

  unsigned long startTime = millis();
  while(millis() - startTime < PUBLISH_DELAY)
  {
    //Trys to reconnect if connection drops
    if (!client.connected())
    {
      reconnect_MQTT();
    }
    client.loop();
  }

  //Publishing to MQTT under business dispense topic
  if(client.publish(topic_business_dispense, businessDispensePayload.c_str())) 
  {
    Serial.println("Dispense successfully sent to dashboard.");
  } 
  else //If error sending data message is displayed
  {
    Serial.println("Failed to send dispense.");
  }

  //Publishing to MQTT under business capacity topic
  if(client.publish(topic_business_capacity, businessCapacityPayload.c_str())) 
  {
    Serial.println("Capacity successfully sent to dashboard.");
  } 
  else //If error sending data message is displayed
  {
    Serial.println("Failed to send capacity.");
  }
}
