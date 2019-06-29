import numpy as np
from pydub import AudioSegment
import random
import sys
import io
import os
import glob
import IPython
from td_utils import *
get_ipython().magic('matplotlib inline')

x = graph_spectrogram("audio_examples/example_train.wav")


_, data = wavfile.read("audio_examples/example_train.wav")
print("Time steps in audio recording before spectrogram", data[:,0].shape)
print("Time steps in input after spectrogram", x.shape)



Tx = 5511 # The number of time steps input to the model from the spectrogram
n_freq = 101 # Number of frequencies input to the model at each time step of the spectrogram

Ty = 1375 # The number of time steps in the output of our model


#- Generating a single training example
# - Pick a random 10 second background audio clip
# - Randomly insert 0-4 audio clips of "activate" into this 10sec clip
# - Randomly insert 0-2 audio clips of negative words into this 10sec clip


# Load audio segments using pydub 
activates, negatives, backgrounds = load_raw_audio()

print("background len: " + str(len(backgrounds[0])))    # Should be 10,000, since it is a 10 sec clip
print("activate[0] len: " + str(len(activates[0])))     # Maybe around 1000, since an "activate" audio clip is usually around 1 sec (but varies a lot)
print("activate[1] len: " + str(len(activates[1])))    


# **Overlaying positive/negative words on the background**:
# 
# 1. get_random_time_segment(segment_ms)` gets a random time segment in our background audio
# 2. is_overlapping(segment_time, existing_segments)` checks if a time segment overlaps with existing segments
# 3. insert_audio_clip(background, audio_clip, existing_times)` inserts an audio segment at a random time in our background audio using `get_random_time_segment` and `is_overlapping`
# 4. insert_ones(y, segment_end_ms)` inserts 1's into our label vector y after the word "activate"



def get_random_time_segment(segment_ms):
    """
    Gets a random time segment of duration segment_ms in a 10,000 ms audio clip.
    
    Arguments:
    segment_ms -- the duration of the audio clip in ms ("ms" stands for "milliseconds")
    
    Returns:
    segment_time -- a tuple of (segment_start, segment_end) in ms
    """
    
    segment_start = np.random.randint(low=0, high=10000-segment_ms)   # Make sure segment doesn't run past the 10sec background 
    segment_end = segment_start + segment_ms - 1
    
    return (segment_start, segment_end)


def is_overlapping(segment_time, previous_segments):
    """
    Checks if the time of a segment overlaps with the times of existing segments.
    
    Arguments:
    segment_time -- a tuple of (segment_start, segment_end) for the new segment
    previous_segments -- a list of tuples of (segment_start, segment_end) for the existing segments
    
    Returns:
    True if the time segment overlaps with any of the existing segments, False otherwise
    """
    
    segment_start, segment_end = segment_time
    overlap = False 
    

    for previous_start, previous_end in previous_segments:
        if  segment_start <= previous_end and segment_end >= previous_start:
            overlap = True

    return overlap


overlap1 = is_overlapping((950, 1430), [(2000, 2550), (260, 949)])
overlap2 = is_overlapping((2305, 2950), [(824, 1532), (1900, 2305), (3424, 3656)])
print("Overlap 1 = ", overlap1)
print("Overlap 2 = ", overlap2)


# 1. Get a random time segment of the right duration in ms.
# 2. Make sure that the time segment does not overlap with any of the previous time segments. If it is overlapping, then go back to step 1 and pick a new time segment.
# 3. Add the new time segment to the list of existing time segments, so as to keep track of all the segments you've inserted.  
# 4. Overlay the audio clip over the background using pydub. We have implemented this for you.

def insert_audio_clip(background, audio_clip, previous_segments):
    """
    Insert a new audio segment over the background noise at a random time step, ensuring that the 
    audio segment does not overlap with existing segments.
    
    Arguments:
    background -- a 10 second background audio recording.  
    audio_clip -- the audio clip to be inserted/overlaid. 
    previous_segments -- times where audio segments have already been placed
    
    Returns:
    new_background -- the updated background audio
    """ 

    segment_ms = len(audio_clip)
    
    segment_time = get_random_time_segment(segment_ms)
    

    while is_overlapping(segment_time, previous_segments) == True:
        segment_time = get_random_time_segment(segment_ms)


    previous_segments.append(segment_time)

    new_background = background.overlay(audio_clip, position = segment_time[0])
    
    return new_background, segment_time


np.random.seed(5)
audio_clip, segment_time = insert_audio_clip(backgrounds[0], activates[0], [(3790, 4400)])
audio_clip.export("insert_test.wav", format="wav")
print("Segment Time: ", segment_time)
IPython.display.Audio("insert_test.wav")


def insert_ones(y, segment_end_ms):
    """
    Update the label vector y. The labels of the 50 output steps strictly after the end of the segment 
    should be set to 1. By strictly we mean that the label of segment_end_y should be 0 while, the
    50 followinf labels should be ones.
    
    
    Arguments:
    y -- numpy array of shape (1, Ty), the labels of the training example
    segment_end_ms -- the end time of the segment in ms
    
    Returns:
    y -- updated labels
    """
    segment_end_y = int(segment_end_ms * Ty / 10000.0)
    
    for i in range(segment_end_y + 1, segment_end_y + 51):
        if i < Ty:
            y[0, i] = 1
    
    return y


# In[18]:

arr1 = insert_ones(np.zeros((1, Ty)), 9700)
plt.plot(insert_ones(arr1, 4251)[0,:])
print("sanity checks:", arr1[0][1333], arr1[0][634], arr1[0][635])

# 1. Initialize the label vector $y$ as a numpy array of zeros and shape $(1, T_y)$.
# 2. Initialize the set of existing segments to an empty list.
# 3. Randomly select 0 to 4 "activate" audio clips, and insert them onto the 10sec clip. Also insert labels at the correct position in the label vector $y$.
# 4. Randomly select 0 to 2 negative audio clips, and insert them into the 10sec clip. 
# 

def create_training_example(background, activates, negatives):
    """
    Creates a training example with a given background, activates, and negatives.
    
    Arguments:
    background -- a 10 second background audio recording
    activates -- a list of audio segments of the word "activate"
    negatives -- a list of audio segments of random words that are not "activate"
    
    Returns:
    x -- the spectrogram of the training example
    y -- the label at each time step of the spectrogram
    """
    
    # Set the random seed
    np.random.seed(18)
    
    # Make background quieter
    background = background - 20

    y = np.zeros((1, Ty))

    previous_segments = []

    number_of_activates = np.random.randint(0, 5)
    random_indices = np.random.randint(len(activates), size=number_of_activates)
    random_activates = [activates[i] for i in random_indices]
    

    for random_activate in random_activates:

        background, segment_time = insert_audio_clip(background, random_activate, previous_segments)

        segment_start, segment_end = segment_time

        y = insert_ones(y, segment_end_ms=segment_end)

    # Select 0-2 random negatives audio recordings from the entire list of "negatives" recordings
    number_of_negatives = np.random.randint(0, 3)
    random_indices = np.random.randint(len(negatives), size=number_of_negatives)
    random_negatives = [negatives[i] for i in random_indices]


    for random_negative in random_negatives:
        # Insert the audio clip on the background 
        background, _ =  insert_audio_clip(background, random_negative, previous_segments)
    
    # Standardize the volume of the audio clip 
    background = match_target_amplitude(background, -20.0)

    # Export new training example 
    file_handle = background.export("train" + ".wav", format="wav")
    print("File (train.wav) was saved in your directory.")
    
    x = graph_spectrogram("train.wav")
    
    return x, y


# In[20]:

x, y = create_training_example(backgrounds[0], activates, negatives)
plt.plot(y[0])

# Load preprocessed training examples
X = np.load("./XY_train/X.npy")
Y = np.load("./XY_train/Y.npy")

# Load preprocessed dev set examples
X_dev = np.load("./XY_dev/X_dev.npy")
Y_dev = np.load("./XY_dev/Y_dev.npy")

from keras.callbacks import ModelCheckpoint
from keras.models import Model, load_model, Sequential
from keras.layers import Dense, Activation, Dropout, Input, Masking, TimeDistributed, LSTM, Conv1D
from keras.layers import GRU, Bidirectional, BatchNormalization, Reshape
from keras.optimizers import Adam



def model(input_shape):
    """
    Function creating the model's graph in Keras.
    
    Argument:
    input_shape -- shape of the model's input data (using Keras conventions)

    Returns:
    model -- Keras model instance
    """
    
    X_input = Input(shape = input_shape)


    X = Conv1D(196, kernel_size=15, strides=4)(X_input)                     
    X = BatchNormalization()(X)                               
    X = Activation('relu')(X)                               
    X = Dropout(0.8)(X)                                 


    X = GRU(units = 128, return_sequences = True)(X)
    X = Dropout(0.8)(X)                           
    X = BatchNormalization()(X)                           

    X = GRU(units = 128, return_sequences = True)(X)  
    X = Dropout(0.8)(X)                                
    X = BatchNormalization()(X)                           
    X = Dropout(0.8)(X)                     
    

    X = TimeDistributed(Dense(1, activation = "sigmoid"))(X) 



    model = Model(inputs = X_input, outputs = X)
    
    return model  

model = model(input_shape = (Tx, n_freq))


model.summary()


model = load_model('./models/tr_model.h5')

opt = Adam(lr=0.0001, beta_1=0.9, beta_2=0.999, decay=0.01)
model.compile(loss='binary_crossentropy', optimizer=opt, metrics=["accuracy"])


model.fit(X, Y, batch_size = 5, epochs=1)

loss, acc = model.evaluate(X_dev, Y_dev)
print("Dev set accuracy = ", acc)


def detect_triggerword(filename):
    plt.subplot(2, 1, 1)

    x = graph_spectrogram(filename)
    x  = x.swapaxes(0,1)
    x = np.expand_dims(x, axis=0)
    predictions = model.predict(x)
    
    plt.subplot(2, 1, 2)
    plt.plot(predictions[0,:,0])
    plt.ylabel('probability')
    plt.show()
    return predictions



chime_file = "audio_examples/chime.wav"
def chime_on_activate(filename, predictions, threshold):
    audio_clip = AudioSegment.from_wav(filename)
    chime = AudioSegment.from_wav(chime_file)
    Ty = predictions.shape[1]
    consecutive_timesteps = 0

    for i in range(Ty):
        consecutive_timesteps += 1
    
        if predictions[0,i,0] > threshold and consecutive_timesteps > 75:

            audio_clip = audio_clip.overlay(chime, position = ((i / Ty) * audio_clip.duration_seconds)*1000)

            consecutive_timesteps = 0
        
    audio_clip.export("chime_output.wav", format='wav')


IPython.display.Audio("./raw_data/dev/1.wav")


IPython.display.Audio("./raw_data/dev/2.wav")

filename = "./raw_data/dev/1.wav"
prediction = detect_triggerword(filename)
chime_on_activate(filename, prediction, 0.5)
IPython.display.Audio("./chime_output.wav")


filename  = "./raw_data/dev/2.wav"
prediction = detect_triggerword(filename)
chime_on_activate(filename, prediction, 0.5)
IPython.display.Audio("./chime_output.wav")


def preprocess_audio(filename):
    padding = AudioSegment.silent(duration=10000)
    segment = AudioSegment.from_wav(filename)[:10000]
    segment = padding.overlay(segment)
    segment = segment.set_frame_rate(44100)
    segment.export(filename, format='wav')


your_filename = "audio_examples/my_audio.wav"


preprocess_audio(your_filename)
IPython.display.Audio(your_filename) # listen to the audio you uploaded 

chime_threshold = 0.5
prediction = detect_triggerword(your_filename)
chime_on_activate(your_filename, prediction, chime_threshold)
IPython.display.Audio("./chime_output.wav")

