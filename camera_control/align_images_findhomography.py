from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import cv2
import imutils
from scipy import ndimage
from time import time

def align_images(image1, image2, maxFeatures=100000, keepPercent=0.005,debug=False):
	# convert both the input image and template to grayscale
	image1 = image1.astype(np.float32)
	image1 = 255 * (image1 - np.min(image1)) / (np.max(image1) - np.min(image1))
	image1 = image1.astype(np.uint8)
	image2 = image2.astype(np.float32)
	image2 = 255 * (image2 - np.min(image2)) / (np.max(image2) - np.min(image2))
	image2 = image2.astype(np.uint8)
	
    # use ORB to detect keypoints and extract (binary) local
	# invariant features
	orb = cv2.ORB_create(maxFeatures)
	(kpsA, descsA) = orb.detectAndCompute(image1, None)
	(kpsB, descsB) = orb.detectAndCompute(image2, None)
	# match the features
	method = cv2.DESCRIPTOR_MATCHER_BRUTEFORCE_HAMMING
	matcher = cv2.DescriptorMatcher_create(method)
	matches = matcher.match(descsA, descsB, None)
	
    # sort the matches by their distance (the smaller the distance,
	# the "more similar" the features are)
	matches = sorted(matches, key=lambda x:x.distance)
	# keep only the top matches
	keep = int(len(matches) * keepPercent)
	matches = matches[:keep]
	# check to see if we should visualize the matched keypoints
	if debug:
		matchedVis = cv2.drawMatches(image1, kpsA, image2, kpsB,
			matches, None)
		matchedVis = imutils.resize(matchedVis, width=1000)
		cv2.imshow("Matched Keypoints", matchedVis)
		cv2.waitKey(0)
		cv2.destroyAllWindows()
	
    # allocate memory for the keypoints (x, y)-coordinates from the
	# top matches -- we'll use these coordinates to compute our
	# homography matrix
	ptsA = np.zeros((len(matches), 2), dtype="float")
	ptsB = np.zeros((len(matches), 2), dtype="float")
	# loop over the top matches
	for (i, m) in enumerate(matches):
		# indicate that the two keypoints in the respective images
		# map to each other
		ptsA[i] = kpsA[m.queryIdx].pt
		ptsB[i] = kpsB[m.trainIdx].pt
	
    # compute the homography matrix between the two sets of matched
	# points
	(H, mask) = cv2.findHomography(ptsA, ptsB, method=cv2.RANSAC)
	# use the homography matrix to align the images
	(h, w) = image2.shape[:2]
	aligned = cv2.warpPerspective(image1, H, (w, h))
	tx = H[0, 2]  # Translation in x-direction
	ty = H[1, 2]  # Translation in y-direction
	print(H)

	return aligned, np.array([ty, tx])





path = str( Path(__file__).absolute() )
temp = path.split('/')

temp[-1] = 'test_images/image_1.npy'
im1 = np.load('/'.join(temp))

temp[-1] = 'test_images/image_4.npy'
im2 = np.load('/'.join(temp))

t0 = time()
aligned, shift = align_images(im1, im2, debug=False)
print(time()-t0, shift, ' homography')


plt.figure()
plt.imshow(im1, alpha=1, cmap='plasma')
plt.imshow(im2, alpha=0.5, cmap='coolwarm')

plt.figure()
plt.imshow(im2, alpha=1, cmap='plasma')
plt.imshow(aligned, alpha=0.5, cmap='coolwarm')

# plt.figure()

# plt.imshow(im2, alpha=1, cmap='plasma')
# aligned = ndimage.shift(im1, shift=shift, mode='nearest')
# plt.imshow(aligned, alpha=0.5, cmap='coolwarm')


plt.show()