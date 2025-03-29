import pathlib
from setuptools import find_packages, setup
from whisper_live.__version__ import __version__


# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="whisper_live_client",
    version=__version__,
    description="Lightweight Python client for WhisperLive — fewer dependencies, optimized for client-only use and easy integration.",
    long_description=README,
    long_description_content_type="text/markdown",
    include_package_data=True,
    url="https://github.com/B4dT0bi/WhisperLiveClient",
    author="Tobias Boese",
    author_email="tobias.boese@gmail.com",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    packages=find_packages(
        exclude=(
            "examples",
            "Audio-Transcription-Chrome",
            "Audio-Transcription-Firefox",
            "requirements",
            "whisper-finetuning"
        )
    ),
    install_requires=[
        "PyAudio",
        "av",
        "scipy",
        "websocket-client"
    ],
    python_requires=">=3.8"
)
