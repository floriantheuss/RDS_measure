from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import cv2
import imutils
from scipy import ndimage
from time import time

# returns image2 but aligned to image1
def align_images(image1, image2, maxFeatures=100000, keepPercent=0.005,debug=False):
	# convert both the input image and template to grayscale
	image1 = image1.astype(np.float32)
	image1 = 255 * (image1 - np.min(image1)) / (np.max(image1) - np.min(image1))
	image1 = image1.astype(np.uint8)
	image2 = image2.astype(np.float32)
	image2 = 255 * (image2 - np.min(image2)) / (np.max(image2) - np.min(image2))
	image2 = image2.astype(np.uint8)
      
	# Step 1: Feature Detection
	orb = cv2.ORB_create(maxFeatures)  # Create ORB detector
	keypoints1, descriptors1 = orb.detectAndCompute(image1, None)
	keypoints2, descriptors2 = orb.detectAndCompute(image2, None)

	# Step 2: Feature Matching
	# method = cv2.NORM_HAMMING
	# bf = cv2.BFMatcher(method, crossCheck=True)
	# matches = bf.match(descriptors1, descriptors2)
	method = cv2.DESCRIPTOR_MATCHER_BRUTEFORCE_HAMMING
	matcher = cv2.DescriptorMatcher_create(method)
	matches = matcher.match(descriptors1, descriptors2, None)
	# sort the matches by their distance (the smaller the distance,
	# the "more similar" the features are)
	matches = sorted(matches, key=lambda x:x.distance)
	# keep only the top matches
	keep = int(len(matches) * keepPercent)
	matches = matches[:keep]

	if debug:
		matchedVis = cv2.drawMatches(image1, keypoints1, image2, keypoints2, matches, None)
		matchedVis = imutils.resize(matchedVis, width=1000)
		cv2.imshow("Matched Keypoints", matchedVis)
		cv2.waitKey(0)
		cv2.destroyAllWindows()

	# Step 3: Extract matched points
	points1 = np.zeros((len(matches), 2), dtype=np.float32)
	points2 = np.zeros((len(matches), 2), dtype=np.float32)

	for i, match in enumerate(matches):
		points1[i, :] = keypoints1[match.queryIdx].pt
		points2[i, :] = keypoints2[match.trainIdx].pt

	# Step 4: Estimate translation using cv2.estimateAffinePartial2D
	# This will give you an affine matrix, but with mostly translation if the points are well chosen
	affine_matrix, inliers = cv2.estimateAffinePartial2D(points1, points2, method=cv2.RANSAC)

	# Step 5: Use the affine matrix to warp the second image
	height, width = image1.shape[:2]
	aligned_image = cv2.warpAffine(image2, -affine_matrix, (width, height))

	return aligned_image, affine_matrix


def find_rotation_and_scaling(affine_matrix):
    # Extract the components
    a11 = affine_matrix[0, 0]
    a12 = affine_matrix[0, 1]
    a21 = affine_matrix[1, 0]
    a22 = affine_matrix[1, 1]

    # Calculate scaling factors
    scale_x = np.sqrt(a11**2 + a21**2)
    scale_y = np.sqrt(a12**2 + a22**2)

    # Normalize for angle calculation
    normalized_a11 = a11 / scale_x
    normalized_a21 = a21 / scale_x
    
    # Calculate rotation angle in radians
    rotation_angle = np.arctan2(normalized_a21, normalized_a11)  # Y, X

    # Convert rotation to degrees
    rotation_angle_degrees = np.degrees(rotation_angle)

    return rotation_angle_degrees, scale_x, scale_y




path = str( Path(__file__).absolute() )
temp = path.split('/')

temp[-1] = 'test_images/image_1.npy'
im1 = np.load('/'.join(temp))

temp[-1] = 'test_images/image_4.npy'
im2 = np.load('/'.join(temp))

t0 = time()
aligned, affine_matrix = align_images(im1, im2, debug=False)
dt = time() - t0
print(find_rotation_and_scaling(affine_matrix))

plt.figure()
plt.imshow(im1, alpha=1, cmap='plasma')
plt.imshow(im2, alpha=0.5, cmap='coolwarm')

plt.figure()
plt.imshow(im1, alpha=1, cmap='plasma')
plt.imshow(aligned, alpha=0.5, cmap='coolwarm')


plt.figure()
plt.imshow(im1, alpha=1, cmap='plasma')
tx = affine_matrix[0, 2]
ty = affine_matrix[1, 2]
# aligned = ndimage.shift(im2, shift=(tx,ty), mode='nearest')
aligned = ndimage.shift(im2, shift=(-ty,-tx), mode='nearest')
plt.imshow(aligned, alpha=0.5, cmap='coolwarm')

print(dt, np.array([tx, ty]), ' affine partial 2D')


plt.show()