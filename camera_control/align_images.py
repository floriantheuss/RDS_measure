from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import cv2
import imutils
from scipy import ndimage
from time import time

class AlignImages:
	def __init__ (self, reference_image, image_to_align, method='affine partial 2D'):
		self.ref_im = reference_image
		self.al_im  = image_to_align
		self.method = method
		if self.method not in ['affine partial 2D', 'homography', 'difference']:
			print ('----------------------------------------------------')
			print ('method must be one of the following:')
			print (['affine partial 2D', 'homography', 'difference'])
			print ('----------------------------------------------------')

	def align_images (self):
		self.proces_images()
		if self.method == 'affine partial 2D':
			aligned_image, affine_matrix = self.align_images_affinepartial2D()
			translation, rotation_angle_degrees, scale_x, scale_y = self.extract_from_affine_matrix(affine_matrix)
		elif self.method == 'homography':
			aligned_image, H = self.align_images_homography()
			translation, rotation_angle_degrees, scale_x, scale_y = self.extract_from_affine_matrix(H)
		elif self.method == 'difference':
			translation = self.align_images_difference()
		return translation
			
	def proces_images (self):
		# convert both the input image and template to grayscale
		self.ref_im = self.ref_im.astype(np.float32)
		self.ref_im = 255 * (self.ref_im - np.min(self.ref_im)) / (np.max(self.ref_im) - np.min(self.ref_im))
		self.ref_im = self.ref_im.astype(np.uint8)
		self.al_im  = self.al_im.astype(np.float32)
		self.al_im  = 255 * (self.al_im - np.min(self.al_im)) / (np.max(self.al_im) - np.min(self.al_im))
		self.al_im  = self.al_im.astype(np.uint8)

	def align_images_difference(self ,image1=None, image2=None, maxFeatures=100000, keepPercent=0.0005,debug=False):
		if image1 is None:
			image1 = self.ref_im
		if image2 is None:
			image2 = self.al_im
		
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
		for i, m in enumerate(matches):
			# indicate that the two keypoints in the respective images
			# map to each other
			ptsA[i] = kpsA[m.queryIdx].pt
			ptsB[i] = kpsB[m.trainIdx].pt

	    ## Step 4: Calculate translation
		translation = np.mean(ptsB - ptsA, axis=0)
		return np.array(translation)
	
	# returns image2 but aligned to image1
	def align_images_affinepartial2D(self, image=None, reference_image=None, maxFeatures=100000, keepPercent=0.005,debug=False):
		if image is None:
			image = self.al_im
		if reference_image is None:
			reference_image = self.ref_im

		# Step 1: Feature Detection
		orb = cv2.ORB_create(maxFeatures)  # Create ORB detector
		keypoints1, descriptors1 = orb.detectAndCompute(image, None)
		keypoints2, descriptors2 = orb.detectAndCompute(reference_image, None)

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
			matchedVis = cv2.drawMatches(image, keypoints1, reference_image, keypoints2, matches, None)
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
		height, width = image.shape[:2]
		aligned_image = cv2.warpAffine(image, affine_matrix, (width, height))

		return aligned_image, affine_matrix
	
	def align_images_homography(self, image=None, reference_image=None, maxFeatures=100000, keepPercent=0.005,debug=False):
		if image is None:
			image = self.al_im
		if reference_image is None:
			reference_image = self.ref_im
    	# use ORB to detect keypoints and extract (binary) local
		# invariant features
		orb = cv2.ORB_create(maxFeatures)
		(kpsA, descsA) = orb.detectAndCompute(image, None)
		(kpsB, descsB) = orb.detectAndCompute(reference_image, None)
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
			matchedVis = cv2.drawMatches(image, kpsA, reference_image, kpsB,
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
		(h, w) = reference_image.shape[:2]
		aligned = cv2.warpPerspective(image, H, (w, h))
		# tx = H[0, 2]  # Translation in x-direction
		# ty = H[1, 2]  # Translation in y-direction

		return aligned, H


	def extract_from_affine_matrix(self, affine_matrix):
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
		rotation_angle = np.arctan2(normalized_a21, normalized_a11)
		# Convert rotation to degrees
		rotation_angle_degrees = np.degrees(rotation_angle)

		shift = np.array([affine_matrix[1, 2], affine_matrix[0, 2]])

		return shift, rotation_angle_degrees, scale_x, scale_y



	
if __name__ == '__main__':	
	path = str( Path(__file__).absolute() )
	temp = path.split('/')

	temp[-1] = 'test_images/image_1.npy'
	ref_im = np.load('/'.join(temp))

	temp[-1] = 'test_images/image_3.npy'
	al_im = np.load('/'.join(temp))

	t0 = time()
	AlIm = AlignImages(reference_image=ref_im, image_to_align=al_im, method='homography')
	shift = AlIm.align_images()#(ref_im, al_im, debug=False)
	print(time()-t0, shift, ' only shift')

	plt.figure()
	plt.imshow(ref_im, alpha=1, cmap='plasma')
	plt.imshow(al_im, alpha=0.5, cmap='coolwarm')


	plt.figure()
	plt.imshow(ref_im, alpha=1, cmap='plasma')
	aligned = ndimage.shift(al_im, shift=shift, mode='nearest')
	plt.imshow(aligned, alpha=0.5, cmap='coolwarm')


	plt.show()