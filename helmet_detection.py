# -*- coding: utf-8 -*-
"""helmet_detection.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1B0_67xJzYe3YeQv-vqpGitsqkFoSdMHY
"""

from google.colab import drive
drive.mount('/content/drive')

import torch
import os

BASE_PATH = "/content/drive/MyDrive/dataset2"
IMAGES_PATH = os.path.sep.join([BASE_PATH, "images"])
ANNOTS_PATH = os.path.sep.join([BASE_PATH, "anotations"])

BASE_OUTPUTS = "/content/drive/MyDrive/output"

MODEL_PATH = os.path.sep.join([BASE_OUTPUTS, "detector.pth"])
LE_PATH = os.path.sep.join([BASE_OUTPUTS, "le.pickle"])
PLOTS_PATH = os.path.sep.join([BASE_OUTPUTS, "plots"])
TEST_PATHS = os.path.sep.join([BASE_OUTPUTS, "test_paths.txt"])

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
PIN_MEMORY = True if DEVICE =="cuda" else False

MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]

INIT_LR = 1e-4
NUM_EPOCHS = 200
BATCH_SIZE = 32

LABELS = 1.0
BBOX = 1.0

#creating dataset
# import the necessary packages
from torch.utils.data import Dataset

class CustomTensorDataset(Dataset):
  def __init__(self, tensors, transforms=None):
    self.tensors = tensors
    self.transforms = transforms

  def __getitem__(self, index):
    image = self.tensors[0][index]
    label = self.tensors[1][index]
    bbox = self.tensors[2][index]

    image = image.permute(2, 0, 1)

    if self.transforms:
      image = self.transforms(image)

    return (image, label, bbox)

  def __len__(self):
    return self.tensors[0].size(0)

from torch.nn import Dropout
from torch.nn import Identity
from torch.nn import Linear
from torch.nn import Module
from torch.nn import ReLU
from torch.nn import Sequential
from torch.nn import Sigmoid

class ObjectDetector(Module):
  def __init__(self, baseModel, numClasses):
    super(ObjectDetector, self).__init__()

    # initialize the base model and the number of classes
    self.baseModel = baseModel
    self.numClasses = numClasses
    # build the regressor head for outputting the bounding box
    # coordinates
    self.regressor = Sequential(
        Linear(baseModel.fc.in_features, 128),
        ReLU(),
        Linear(128, 64),
        ReLU(),
        Linear(64, 32),
        ReLU(),
        Linear(32, 4),
        Sigmoid()
    )
    # build the classifier head to predict the class labels
    self.classifier = Sequential(
        Linear(baseModel.fc.in_features, 512),
        ReLU(),
        Dropout(),
        Linear(512, 512),
        ReLU(),
        Dropout(),
        Linear(512, self.numClasses)
    )

    self.baseModel.fc = Identity()

  def forward(self, x):
    # pass the inputs through the base model and then obtain
    # predictions from two different branches of the network
    # predictions from two different branches of the network
    features = self.baseModel(x)
    bboxes = self.regressor(features)
    classLogits = self.classifier(features)
    return (bboxes, classLogits)

from sklearn.preprocessing import LabelEncoder
from torch.utils.data import DataLoader
from torchvision import transforms
from torch.nn import CrossEntropyLoss
from torch.nn import MSELoss
from torch.optim import Adam
from torchvision.models import resnet50
from sklearn.model_selection import train_test_split
from imutils import paths
from tqdm import tqdm
import matplotlib.pyplot as plt
import numpy as np
import pickle
import torch
import time
import cv2
import os

print("[INFO] loading dataset...")
data = []
labels = []
bboxes = []
imagePaths = []

h= 416
w = 416
h = float(h)
w = float(w)
i = 0

for csvPath in paths.list_files(ANNOTS_PATH, validExts=(".csv")):
  print(csvPath)
  # load the contents of the current CSV annotations file
  rows = open(csvPath).read().strip().split("\n")
  print(rows[1])
  # loop over the rows
  for row in rows[1:]:
    # break the row into the filename, bounding box coordinates,
    # and class label
    row = row.split(",")
    (filename, width, height, label, startX, startY, endX, endY) = row
    # derive the path to the input image, load the image (in
    # OpenCV format), and grab its dimensions
    ##print(filename)
    imagePath = os.path.sep.join([IMAGES_PATH,
    	filename])
    ##print(imagePath)
    image = cv2.imread(imagePath)
    #(h, w) = image.shape[:2]
    # scale the bounding box coordinates relative to the spatial
    # dimensions of the input image
    startX = float(startX) / w
    startY = float(startY) / h
    endX = float(endX) / w
    endY = float(endY) / h
    # load the image and preprocess it
    image = cv2.imread(imagePath)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = cv2.resize(image, (224, 224))
    # update our list of data, class labels, bounding boxes, and
    # image paths
    data.append(image)
    labels.append(label)
    bboxes.append((startX, startY, endX, endY))
    imagePaths.append(imagePath)
    i+=1
    print(f"finished reading row: {i}")

#convert the data ,class labels bounding boxes and imagepaths to numpy arrays
data = np.array(data, dtype="float32")
labels = np.array(labels)
bboxes = np.array(bboxes, dtype="float32")
imagePaths = np.array(imagePaths)

#perform label encoding on the labels
le = LabelEncoder()
labels = le.fit_transform(labels)

#partition the data into traing and testing splits using 80% and 20%
split = train_test_split(data, labels, bboxes, imagePaths,test_size=0.20, random_state=42)
(trainImages, testImages) = split[:2]
(trainLabels, testLabels) = split[2:4]
(trainBBoxes, testBBoxes) = split[4:6]
(trainPaths, testPaths) = split[6:]

#converting numpy arrays into pytorch tensors
(trainImages, testImages) = torch.tensor(trainImages), torch.tensor(testImages)
(trainLabels, testLabels) = torch.tensor(trainLabels), torch.tensor(testLabels)
(trainBBoxes, testBBoxes) = torch.tensor(trainBBoxes), torch.tensor(testBBoxes)

# define normalization transforms
transforms = transforms.Compose([
	transforms.ToPILImage(),
	transforms.ToTensor(),
	transforms.Normalize(mean=MEAN, std=STD)
])

# convert NumPy arrays to PyTorch datasets
trainDS = CustomTensorDataset((trainImages, trainLabels, trainBBoxes),
	transforms=transforms)
testDS = CustomTensorDataset((testImages, testLabels, testBBoxes),
	transforms=transforms)
print("[INFO] total training samples: {}...".format(len(trainDS)))
print("[INFO] total test samples: {}...".format(len(testDS)))

# calculate steps per epoch for training and validation set
trainSteps = len(trainDS) // BATCH_SIZE
valSteps = len(testDS) // BATCH_SIZE

# create data loaders
trainLoader = DataLoader(trainDS, batch_size=BATCH_SIZE,
	shuffle=True, num_workers=os.cpu_count(), pin_memory=PIN_MEMORY)
testLoader = DataLoader(testDS, batch_size=BATCH_SIZE,
	num_workers=os.cpu_count(), pin_memory=PIN_MEMORY)

# write the testing image paths to disk so that we can use then
# when evaluating/testing our object detector
print("[INFO] saving testing image paths...")
f = open(TEST_PATHS, "w")
f.write("\n".join(testPaths))
f.close()

# load the ResNet50 network
resnet = resnet50(pretrained=True)

# freeze all ResNet50 layers so they will *not* be updated during the
# training process
for param in resnet.parameters():
	param.requires_grad = False

# create our custom object detector model and flash it to the current
# device
objectDetector = ObjectDetector(resnet, len(le.classes_))
objectDetector = objectDetector.to(DEVICE)

print(len(le.classes_))

# define our loss functions
classLossFunc = CrossEntropyLoss()
bboxLossFunc = MSELoss()

# initialize the optimizer, compile the model, and show the model
# summary
opt = Adam(objectDetector.parameters(), lr=INIT_LR)
print(objectDetector)

# initialize a dictionary to store training history
H = {"total_train_loss": [], "total_val_loss": [], "train_class_acc": [],
	 "val_class_acc": []}

# loop over epochs
print("[INFO] training the network...")
startTime = time.time()
for e in tqdm(range(NUM_EPOCHS)):
  # set the model in training mode
  objectDetector.train()

  # initialize the total training and validation loss
  totalTrainLoss = 0
  totalValLoss = 0  

  # initialize the number of correct predictions in the training
  # and validation step
  trainCorrect = 0
  valCorrect = 0
  
  # loop over the training set
  for (images, labels, bboxes) in trainLoader:
    # send the input to the device
    (images, labels, bboxes) = (images.to(DEVICE),	labels.to(DEVICE), bboxes.to(DEVICE))    
    #performing forward pass and calculate the training loss
    predictions = objectDetector(images)
    bboxLoss = bboxLossFunc(predictions[0], bboxes)
    classLoss = classLossFunc(predictions[1], labels)
    totalLoss = (BBOX * bboxLoss) + (LABELS * classLoss)  
    ## zero out the gradients, perform the backpropagation step,and u[pdate the weights
    opt.zero_grad()
    totalLoss.backward()
    opt.step()
    totalTrainLoss += totalLoss
    trainCorrect += (predictions[1].argmax(1) == labels).type(torch.float).sum().item() 

	# switch off autograd
  with torch.no_grad():
    # set the model in evaluation mode
    objectDetector.eval()
    # loop over the validation set
    for (images, labels, bboxes) in testLoader:
      # send the input to the device
      (images, labels, bboxes) = (images.to(DEVICE),
      	labels.to(DEVICE), bboxes.to(DEVICE))
      # make the predictions and calculate the validation loss
      predictions = objectDetector(images)
      bboxLoss = bboxLossFunc(predictions[0], bboxes)
      classLoss = classLossFunc(predictions[1], labels)
      totalLoss = (BBOX * bboxLoss) + \
      	(LABELS * classLoss)
      totalValLoss += totalLoss
      # calculate the number of correct predictions
      valCorrect += (predictions[1].argmax(1) == labels).type(
      	torch.float).sum().item()  
       
  	# calculate the average training and validation loss
  avgTrainLoss = totalTrainLoss / trainSteps
  avgValLoss = totalValLoss / valSteps
  # calculate the training and validation accuracy
  trainCorrect = trainCorrect / len(trainDS)
  valCorrect = valCorrect / len(testDS)
  # update our training history
  H["total_train_loss"].append(avgTrainLoss.cpu().detach().numpy())
  H["train_class_acc"].append(trainCorrect)
  H["total_val_loss"].append(avgValLoss.cpu().detach().numpy())
  H["val_class_acc"].append(valCorrect)
  # print the model training and validation information
  print("[INFO] EPOCH: {}/{}".format(e + 1, NUM_EPOCHS))
  print("Train loss: {:.6f}, Train accuracy: {:.4f}".format(
  	avgTrainLoss, trainCorrect))
  print("Val loss: {:.6f}, Val accuracy: {:.4f}".format(
  	avgValLoss, valCorrect))
  endTime = time.time()
  print("[INFO] total time taken to train the model: {:.2f}s".format(
  endTime - startTime))

# serialize the model to disk
print("[INFO] saving object detector model...")
torch.save(objectDetector, MODEL_PATH)
# serialize the label encoder to disk
print("[INFO] saving label encoder...")
f = open(LE_PATH, "wb")
f.write(pickle.dumps(le))
f.close()
# plot the training loss and accuracy
plt.style.use("ggplot")
plt.figure()
plt.plot(H["total_train_loss"], label="total_train_loss")
plt.plot(H["total_val_loss"], label="total_val_loss")
plt.plot(H["train_class_acc"], label="train_class_acc")
plt.plot(H["val_class_acc"], label="val_class_acc")
plt.title("Total Training Loss and Classification Accuracy on Dataset")
plt.xlabel("Epoch #")
plt.ylabel("Loss/Accuracy")
plt.legend(loc="lower left")
# save the training plot
plotPath = os.path.sep.join([PLOTS_PATH, "training.png"])
plt.savefig(plotPath)

# USAGE
# python predict.py --input dataset/images/face/image_0131.jpg
# import the necessary packages
# from pyimagesearch import config
from google.colab.patches import cv2_imshow
from torchvision import transforms
import mimetypes
import argparse
import imutils
import pickle
import torch
import cv2
# construct the argument parser and parse the arguments
# ap = argparse.ArgumentParser()
# ap.add_argument("-i", "--input", required=True,help="path to input image/text file of image paths")
# args = vars(ap.parse_args())

#load ur image here
imagePath = '/content/drive/MyDrive/dataset2/images.jpg'

#load our object detector set it evaluation mode , and label encoder from drive
print('[info loading object detector ....]')
model = torch.load(MODEL_PATH).to(DEVICE)
model.eval()
le = pickle.loads(open(LE_PATH, "rb").read())

#define normalization transforms
transforms = transforms.Compose([
    transforms.ToPILImage(),
    transforms.ToTensor(),
    transforms.Normalize(mean = MEAN, std= STD)
])

# loop over the image that we'll be testing out bounding box
#regression model
# or imagePath in imagePaths:
image = cv2.imread(imagePath)
original = image.copy()
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
image = cv2.resize(image,(224, 244))
image = image.transpose((2, 0, 1))
image = torch.from_numpy(image)
image = transforms(image).to(DEVICE)
image = image.unsqueeze(0)
(boxPreds, labelPreds) = model(image)
(startX, startY, endX, endY) = boxPreds[0]
labelPreds = torch.nn.Softmax(dim=-1)(labelPreds)
i = labelPreds.argmax(dim=-1).cpu()
label = le.inverse_transform(i)[0]
original = imutils.resize(original, width=600)
(h, w) = original.shape[:2]
startX = int(startX * w)
startY = int(startY * h)
endX = int(endX * w)
endY = int(endY * h)
y = startY - 10 if startY - 10 > 10 else startY +1
cv2.putText(original, label,(startX, y),cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
cv2.rectangle(original, (startX,startY),(endX,endY), (0,255,0), 2)
cv2_imshow(original)