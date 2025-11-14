"""Setup script for the pricing library."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pricing-library",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A flexible Python library for managing products with free, paid, credit, and mixed pricing systems",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/pricing-library",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: FastAPI",
    ],
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.104.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "httpx>=0.25.0",
            "uvicorn>=0.24.0",
        ],
        "full": [
            "uvicorn>=0.24.0",
            "python-multipart>=0.0.6",
        ],
    },
    package_data={
        "pricing_library": ["py.typed"],
    },
)
