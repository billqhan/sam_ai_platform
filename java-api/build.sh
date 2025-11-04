#!/bin/bash

# RFP Response Agent Java API Build Script

echo "🚀 Building RFP Response Agent Java API..."

# Check if Maven is installed
if ! command -v mvn &> /dev/null; then
    echo "❌ Maven is not installed. Please install Maven 3.8+ to continue."
    exit 1
fi

# Check Java version
JAVA_VERSION=$(java -version 2>&1 | grep -oP 'version "?\K[^"]+' | head -1)
if [[ ${JAVA_VERSION%.*} < "17" ]]; then
    echo "❌ Java 17 or higher is required. Current version: $JAVA_VERSION"
    exit 1
fi

echo "✅ Java version: $JAVA_VERSION"

# Clean and compile
echo "🧹 Cleaning previous builds..."
mvn clean

echo "🔨 Compiling sources..."
mvn compile

# Run tests
echo "🧪 Running tests..."
mvn test

# Package application
echo "📦 Packaging application..."
mvn package -DskipTests

# Check if JAR was created
JAR_FILE=$(find target -name "*.jar" -not -name "*-sources.jar" | head -1)
if [[ -f "$JAR_FILE" ]]; then
    echo "✅ Build successful! JAR created: $JAR_FILE"
    echo ""
    echo "🎯 Next steps:"
    echo "   • Run locally: java -jar $JAR_FILE"
    echo "   • Build Docker image: docker build -t rfp-api ."
    echo "   • Run with Docker Compose: docker-compose up"
    echo ""
    echo "📊 API will be available at:"
    echo "   • Health: http://localhost:8080/api/health"
    echo "   • Dashboard: http://localhost:8080/api/dashboard/metrics"
    echo "   • OpenAPI: http://localhost:8080/api/swagger-ui.html"
else
    echo "❌ Build failed! JAR file not found."
    exit 1
fi